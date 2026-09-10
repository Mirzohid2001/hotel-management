from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from .models import Employee, PayrollItem, PayrollPeriod, SalaryAdvance, SalaryPayment


@transaction.atomic
def create_advance(
    tenant,
    employee: Employee,
    *,
    amount: Decimal,
    advance_date=None,
    note: str = "",
) -> SalaryAdvance:
    if employee.tenant_id != tenant.pk:
        raise ValidationError(_("Xodim ushbu mehmonxonaga tegishli emas."))
    if amount is None or Decimal(amount) <= 0:
        raise ValidationError(_("Avans summasi musbat bo‘lishi kerak."))
    return SalaryAdvance.objects.create(
        tenant=tenant,
        employee=employee,
        amount=Decimal(amount),
        advance_date=advance_date or timezone.localdate(),
        note=(note or "").strip(),
    )


@transaction.atomic
def settle_advance(advance: SalaryAdvance) -> SalaryAdvance:
    if advance.is_settled:
        raise ValidationError(_("Avans allaqachon hisoblangan."))
    if advance.applied_to_period_id and advance.applied_to_period.status != PayrollPeriod.Status.DRAFT:
        raise ValidationError(_("Avans yakunlangan ish haqi davrida qulflangan."))
    advance.is_settled = True
    advance.applied_to_period = None
    advance.save(update_fields=["is_settled", "applied_to_period", "updated_at"])
    return advance


def _advances_for_employee(employee: Employee, period: PayrollPeriod):
    return SalaryAdvance.objects.filter(
        employee=employee,
        is_settled=False,
    ).filter(Q(applied_to_period__isnull=True) | Q(applied_to_period=period))


def _max_advance_deduction(item: PayrollItem) -> Decimal:
    due = (item.base_amount or Decimal("0")) + (item.bonus or Decimal("0")) - (
        item.deduction or Decimal("0")
    )
    return due if due > 0 else Decimal("0")


@transaction.atomic
def sync_item_advances(item: PayrollItem) -> PayrollItem:
    """
    Ochiq avanslarni oylik qatoriga bog‘lash (sof >= 0).
    To‘lovdan oldin chaqiriladi — yakunlangan davrda ham.
    """
    if SalaryPayment.objects.filter(item=item).exists():
        return item

    period = item.period
    SalaryAdvance.objects.filter(
        employee_id=item.employee_id,
        applied_to_period=period,
        is_settled=False,
    ).update(applied_to_period=None)

    max_deduct = _max_advance_deduction(item)
    open_qs = _advances_for_employee(item.employee, period).order_by(
        "advance_date", "pk"
    )
    open_total = open_qs.aggregate(s=Sum("amount_base"))["s"] or Decimal("0")
    to_apply = min(open_total, max_deduct)

    linked = Decimal("0")
    for adv in open_qs:
        if linked >= to_apply:
            break
        amt = adv.amount_base if adv.amount_base is not None else adv.amount
        if linked + amt > to_apply:
            # Katta avans: ushlanma raqamda bo‘ladi, yozuv ochiq qoladi (keyingi oy)
            continue
        adv.applied_to_period = period
        adv.save(update_fields=["applied_to_period", "updated_at"])
        linked += amt

    item.advance = to_apply
    item.save()
    return item


@transaction.atomic
def generate_payroll(tenant, year: int, month: int) -> PayrollPeriod:
    period, _created = PayrollPeriod.objects.get_or_create(
        tenant=tenant, year=year, month=month, defaults={"status": PayrollPeriod.Status.DRAFT}
    )
    if period.status != PayrollPeriod.Status.DRAFT:
        raise ValidationError(_("Davr qoralama emas."))

    SalaryAdvance.objects.filter(applied_to_period=period, is_settled=False).update(
        applied_to_period=None
    )

    for emp in Employee.objects.filter(tenant=tenant, is_active=True):
        item, _created = PayrollItem.objects.get_or_create(
            tenant=tenant,
            period=period,
            employee=emp,
            defaults={"base_amount": emp.base_salary},
        )
        if item.base_amount == 0 and emp.base_salary:
            item.base_amount = emp.base_salary
            item.save(update_fields=["base_amount", "updated_at"])
        if SalaryPayment.objects.filter(item=item).exists():
            continue
        sync_item_advances(item)

    return period


@transaction.atomic
def finalize_payroll(period: PayrollPeriod) -> PayrollPeriod:
    if period.status != PayrollPeriod.Status.DRAFT:
        raise ValidationError(_("Faqat qoralama davrlar yakunlanadi."))
    if not period.items.exists():
        raise ValidationError(_("Davrda ish haqi qatorlari yo‘q."))
    SalaryAdvance.objects.filter(applied_to_period=period, is_settled=False).update(
        is_settled=True
    )
    period.status = PayrollPeriod.Status.FINALIZED
    period.save(update_fields=["status", "updated_at"])
    return period


def open_advance_total(employee: Employee) -> Decimal:
    return (
        SalaryAdvance.objects.filter(employee=employee, is_settled=False).aggregate(
            s=Sum("amount_base")
        )["s"]
        or Decimal("0")
    )


def salary_due_preview(employee: Employee) -> Decimal:
    """Taxminiy sof oylik: baza − ochiq avanslar (0 dan pastga tushmasin)."""
    due = Decimal(employee.base_salary or 0) - open_advance_total(employee)
    return due if due > 0 else Decimal("0")


@transaction.atomic
def update_payroll_item_amounts(
    item: PayrollItem,
    *,
    bonus: Decimal | None = None,
    deduction: Decimal | None = None,
) -> PayrollItem:
    if SalaryPayment.objects.filter(item=item).exists():
        raise ValidationError(_("To‘langan qatorni o‘zgartirib bo‘lmaydi."))
    if bonus is not None:
        if Decimal(bonus) < 0:
            raise ValidationError(_("Bonus manfiy bo‘lmasligi kerak."))
        item.bonus = Decimal(bonus)
    if deduction is not None:
        if Decimal(deduction) < 0:
            raise ValidationError(_("Ushlama manfiy bo‘lmasligi kerak."))
        item.deduction = Decimal(deduction)
    item.save()
    return sync_item_advances(item)


@transaction.atomic
def mark_item_paid(item: PayrollItem, amount=None, method="cash") -> SalaryPayment:
    period = item.period
    if SalaryPayment.objects.filter(item=item).exists():
        raise ValidationError(_("Bu qator allaqachon to‘langan."))

    # Avanslarni to‘lovdan oldin yangilash (yakunlangan davrda ham)
    if period.status == PayrollPeriod.Status.DRAFT:
        generate_payroll(period.tenant, period.year, period.month)
        item.refresh_from_db()
        sync_item_advances(item)
        item.refresh_from_db()
        finalize_payroll(period)
        period.refresh_from_db()
        item.refresh_from_db()
    else:
        sync_item_advances(item)
        item.refresh_from_db()
        # Bog‘langan avanslarni yopish (finalize o‘tkazilmagan bo‘lsa)
        SalaryAdvance.objects.filter(
            applied_to_period=period,
            employee_id=item.employee_id,
            is_settled=False,
        ).update(is_settled=True)

    if amount is None:
        amount = item.net_amount if item.net_amount > 0 else Decimal("0")
    elif Decimal(amount) < 0:
        raise ValidationError(_("To‘lov summasi manfiy bo‘lmasligi kerak."))

    payment, _created = SalaryPayment.objects.update_or_create(
        item=item,
        defaults={
            "tenant": item.tenant,
            "amount": amount,
            "paid_at": timezone.now(),
            "method": method,
        },
    )
    unpaid = item.period.items.filter(payment__isnull=True).exists()
    if not unpaid:
        item.period.status = PayrollPeriod.Status.PAID
        item.period.save(update_fields=["status", "updated_at"])
    return payment


@transaction.atomic
def pay_employee_salary(
    tenant,
    employee: Employee,
    *,
    year: int | None = None,
    month: int | None = None,
    method: str = "cash",
) -> SalaryPayment:
    """Bitta tugma: shu oy uchun generatsiya → yakunlash → to‘lash."""
    if employee.tenant_id != tenant.pk:
        raise ValidationError(_("Xodim ushbu mehmonxonaga tegishli emas."))
    if not employee.is_active:
        raise ValidationError(_("Faol bo‘lmagan xodimga oylik berib bo‘lmaydi."))

    today = timezone.localdate()
    year = year or today.year
    month = month or today.month

    period, _created = PayrollPeriod.objects.get_or_create(
        tenant=tenant,
        year=year,
        month=month,
        defaults={"status": PayrollPeriod.Status.DRAFT},
    )
    if period.status == PayrollPeriod.Status.DRAFT:
        generate_payroll(tenant, year, month)

    try:
        item = PayrollItem.objects.select_related("period").get(
            period=period, employee=employee
        )
    except PayrollItem.DoesNotExist as exc:
        raise ValidationError(
            _("Bu oy uchun qator yo‘q. Xodim yakunlangan davrdan keyin qo‘shilgan bo‘lishi mumkin.")
        ) from exc

    return mark_item_paid(item, method=method)


@transaction.atomic
def pay_all_unpaid(
    tenant,
    *,
    year: int | None = None,
    month: int | None = None,
    method: str = "cash",
) -> int:
    """Shu oydagi barcha to‘lanmagan oyliklarni bir martada to‘lash."""
    today = timezone.localdate()
    year = year or today.year
    month = month or today.month

    period, _created = PayrollPeriod.objects.get_or_create(
        tenant=tenant,
        year=year,
        month=month,
        defaults={"status": PayrollPeriod.Status.DRAFT},
    )
    if period.status == PayrollPeriod.Status.DRAFT:
        generate_payroll(tenant, year, month)

    paid = 0
    for item in period.items.select_related("employee"):
        if SalaryPayment.objects.filter(item=item).exists():
            continue
        mark_item_paid(item, method=method)
        paid += 1
    return paid
