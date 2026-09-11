from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import Employee, PayrollItem, PayrollPeriod, SalaryAdvance, SalaryPayment

ZERO = Decimal("0")


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
    if not employee.is_active:
        raise ValidationError(_("Faol bo‘lmagan xodimga avans berib bo‘lmaydi."))
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
    """Qo‘lda yopish — qolgan qarzni kechirish."""
    if advance.is_settled:
        raise ValidationError(_("Avans allaqachon hisoblangan."))
    principal = advance.principal
    advance.recovered_amount = principal
    advance.is_settled = True
    advance.applied_to_period = None
    advance.save(
        update_fields=["recovered_amount", "is_settled", "applied_to_period", "updated_at"]
    )
    return advance


def _open_advances_qs(employee: Employee):
    return (
        SalaryAdvance.objects.filter(employee=employee, is_settled=False)
        .order_by("advance_date", "pk")
    )


def open_advance_total(employee: Employee) -> Decimal:
    total = ZERO
    for adv in _open_advances_qs(employee):
        total += adv.open_amount
    return total


def salary_due_preview(employee: Employee, *, days: int = 1) -> Decimal:
    """
    Taxminiy sof to‘lov: stavka (−× kun) − ochiq avanslar.
    Oylik: oyiga; kunlik: days × kunlik stavka.
    """
    rate = Decimal(employee.base_salary or 0)
    if employee.is_daily:
        days = max(1, int(days or 1))
        gross = rate * days
    else:
        gross = rate
    due = gross - open_advance_total(employee)
    return due if due > 0 else ZERO


def _max_advance_deduction(item: PayrollItem) -> Decimal:
    return item.gross_amount


def preview_advance_deduction(employee: Employee, item: PayrollItem) -> Decimal:
    """Shu qatordan ushlanadigan avans (hali yozilmagan)."""
    return min(open_advance_total(employee), _max_advance_deduction(item))


@transaction.atomic
def sync_item_advances(item: PayrollItem) -> PayrollItem:
    """Ochiq avans qoldig‘ini qatorga yozish (sof >= 0). To‘lovdan oldin."""
    if SalaryPayment.objects.filter(item=item).exists():
        return item
    item.advance = preview_advance_deduction(item.employee, item)
    item.save(update_fields=["advance", "net_amount", "updated_at"])
    return item


@transaction.atomic
def recover_advances(
    employee: Employee,
    amount: Decimal,
    *,
    period: PayrollPeriod | None = None,
) -> Decimal:
    """
    To‘lovdan ushlangan summani avanslarga FIFO bilan yozish.
    Qisman qoplash: recovered_amount oshadi; to‘liq bo‘lsa is_settled=True.
    """
    left = Decimal(amount or 0)
    if left <= 0:
        return ZERO
    recovered = ZERO
    for adv in _open_advances_qs(employee).select_for_update():
        if left <= 0:
            break
        open_amt = adv.open_amount
        if open_amt <= 0:
            adv.is_settled = True
            adv.save(update_fields=["is_settled", "updated_at"])
            continue
        take = min(open_amt, left)
        adv.recovered_amount = (adv.recovered_amount or ZERO) + take
        if period is not None:
            adv.applied_to_period = period
        if adv.open_amount <= 0:
            adv.is_settled = True
        adv.save(
            update_fields=[
                "recovered_amount",
                "is_settled",
                "applied_to_period",
                "updated_at",
            ]
        )
        left -= take
        recovered += take
    return recovered


def _monthly_employees(tenant):
    return Employee.objects.filter(
        tenant=tenant,
        is_active=True,
        salary_type=Employee.SalaryType.MONTHLY,
    )


@transaction.atomic
def generate_payroll(tenant, year: int, month: int) -> PayrollPeriod:
    """Faqat oylik xodimlar — kunliklar alohida kunlik to‘lov bilan.
    Kunlik to‘lovdan keyin davr FINALIZED/PAID bo‘lsa ham oylik qatorlar qo‘shiladi.
    """
    period, _created = PayrollPeriod.objects.get_or_create(
        tenant=tenant, year=year, month=month, defaults={"status": PayrollPeriod.Status.DRAFT}
    )

    for emp in _monthly_employees(tenant):
        item, _created = PayrollItem.objects.get_or_create(
            tenant=tenant,
            period=period,
            employee=emp,
            work_date=None,
            defaults={"base_amount": emp.base_salary, "days_count": 1},
        )
        if SalaryPayment.objects.filter(item=item).exists():
            continue
        if item.base_amount == 0 and emp.base_salary:
            item.base_amount = emp.base_salary
            item.days_count = 1
            item.save(update_fields=["base_amount", "days_count", "updated_at"])
        sync_item_advances(item)

    period.refresh_from_db()
    if (
        period.status == PayrollPeriod.Status.PAID
        and period.items.filter(payment__isnull=True).exists()
    ):
        period.status = PayrollPeriod.Status.FINALIZED
        period.save(update_fields=["status", "updated_at"])
    return period


@transaction.atomic
def finalize_payroll(period: PayrollPeriod) -> PayrollPeriod:
    """Davrni qulflash — avanslar to‘lov paytida qoplansin."""
    if period.status not in {
        PayrollPeriod.Status.DRAFT,
        PayrollPeriod.Status.FINALIZED,
    }:
        raise ValidationError(_("To‘liq to‘langan davrni qayta yakunlab bo‘lmaydi."))
    if not period.items.exists():
        raise ValidationError(_("Davrda ish haqi qatorlari yo‘q."))
    for item in period.items.filter(payment__isnull=True).select_related("employee"):
        sync_item_advances(item)
    period.status = PayrollPeriod.Status.FINALIZED
    period.save(update_fields=["status", "updated_at"])
    return period


def ensure_payroll_item(
    tenant,
    employee: Employee,
    *,
    year: int,
    month: int,
) -> PayrollItem:
    """Oylik xodim uchun oy qatorini topish yoki yaratish."""
    if employee.is_daily:
        raise ValidationError(
            _("Kunlik xodim uchun oylik qator yaratilmaydi — kunlik to‘lovdan foydalaning.")
        )
    period, _created = PayrollPeriod.objects.get_or_create(
        tenant=tenant,
        year=year,
        month=month,
        defaults={"status": PayrollPeriod.Status.DRAFT},
    )
    if period.status == PayrollPeriod.Status.DRAFT:
        generate_payroll(tenant, year, month)
        return PayrollItem.objects.select_related("period", "employee").get(
            period=period, employee=employee, work_date__isnull=True
        )

    item, created = PayrollItem.objects.get_or_create(
        tenant=tenant,
        period=period,
        employee=employee,
        work_date=None,
        defaults={"base_amount": employee.base_salary or ZERO, "days_count": 1},
    )
    if created or (
        not SalaryPayment.objects.filter(item=item).exists()
        and item.base_amount == 0
        and employee.base_salary
    ):
        if item.base_amount == 0 and employee.base_salary:
            item.base_amount = employee.base_salary
            item.days_count = 1
            item.save(update_fields=["base_amount", "days_count", "updated_at"])
    return item


def ensure_daily_payroll_item(
    tenant,
    employee: Employee,
    *,
    work_date: date,
    days: int = 1,
) -> PayrollItem:
    """Kunlik xodim: ish kuni qatori (stavka × kun)."""
    if not employee.is_daily:
        raise ValidationError(_("Bu xodim oylik — oddiy oylik to‘lovdan foydalaning."))
    days = int(days or 1)
    if days < 1 or days > 31:
        raise ValidationError(_("Kunlar soni 1–31 oralig‘ida bo‘lishi kerak."))
    rate = Decimal(employee.base_salary or 0)
    if rate <= 0:
        raise ValidationError(_("Kunlik stavka kiritilmagan."))
    base = (rate * days).quantize(Decimal("0.01"))

    period, _created = PayrollPeriod.objects.get_or_create(
        tenant=tenant,
        year=work_date.year,
        month=work_date.month,
        defaults={"status": PayrollPeriod.Status.DRAFT},
    )
    item, created = PayrollItem.objects.get_or_create(
        tenant=tenant,
        period=period,
        employee=employee,
        work_date=work_date,
        defaults={"base_amount": base, "days_count": days},
    )
    if SalaryPayment.objects.filter(item=item).exists():
        raise ValidationError(
            _("%(d)s kuni allaqachon to‘langan.") % {"d": work_date.strftime("%d.%m.%Y")}
        )
    if not created and (item.base_amount != base or item.days_count != days):
        item.base_amount = base
        item.days_count = days
        item.bonus = ZERO
        item.deduction = ZERO
        item.save(
            update_fields=[
                "base_amount",
                "days_count",
                "bonus",
                "deduction",
                "net_amount",
                "updated_at",
            ]
        )
    return item


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

    # Kunlik qator: oy jadvalini majburan generate/finalize qilmaymiz
    if item.work_date is None and period.status == PayrollPeriod.Status.DRAFT:
        generate_payroll(period.tenant, period.year, period.month)
        item.refresh_from_db()
        if period.status == PayrollPeriod.Status.DRAFT:
            finalize_payroll(period)
        period.refresh_from_db()
        item.refresh_from_db()

    sync_item_advances(item)
    item.refresh_from_db()

    if amount is None:
        amount = item.net_amount
    amount = Decimal(amount)
    if amount < 0:
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

    recover_advances(item.employee, item.advance or ZERO, period=period)

    unpaid = item.period.items.filter(payment__isnull=True).exists()
    if not unpaid:
        item.period.status = PayrollPeriod.Status.PAID
        item.period.save(update_fields=["status", "updated_at"])
    elif item.period.status == PayrollPeriod.Status.DRAFT:
        item.period.status = PayrollPeriod.Status.FINALIZED
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
    """Oylik xodim: shu oy uchun qator → avans ushlash → to‘lash."""
    if employee.tenant_id != tenant.pk:
        raise ValidationError(_("Xodim ushbu mehmonxonaga tegishli emas."))
    if not employee.is_active:
        raise ValidationError(_("Faol bo‘lmagan xodimga oylik berib bo‘lmaydi."))
    if employee.is_daily:
        raise ValidationError(
            _("Bu xodim kunlik — «Kunlik to‘lash» orqali bering (kunlar soni bilan).")
        )

    today = timezone.localdate()
    year = year or today.year
    month = month or today.month

    item = ensure_payroll_item(tenant, employee, year=year, month=month)
    return mark_item_paid(item, method=method)


@transaction.atomic
def pay_employee_daily(
    tenant,
    employee: Employee,
    *,
    days: int = 1,
    work_date: date | None = None,
    method: str = "cash",
) -> SalaryPayment:
    """
    Kunlik xodim: stavka × kun → avans ushlash → to‘lash.
    Sof (P&L): yalpi base; kassa: sof to‘lov (net). Bir kunda bir marta.
    """
    if employee.tenant_id != tenant.pk:
        raise ValidationError(_("Xodim ushbu mehmonxonaga tegishli emas."))
    if not employee.is_active:
        raise ValidationError(_("Faol bo‘lmagan xodimga kunlik berib bo‘lmaydi."))
    if not employee.is_daily:
        raise ValidationError(_("Bu xodim oylik — «Oylik to‘lash»dan foydalaning."))

    work_date = work_date or timezone.localdate()
    item = ensure_daily_payroll_item(
        tenant, employee, work_date=work_date, days=days
    )
    return mark_item_paid(item, method=method)


@transaction.atomic
def pay_all_unpaid(
    tenant,
    *,
    year: int | None = None,
    month: int | None = None,
    method: str = "cash",
) -> int:
    """Shu oydagi to‘lanmagan OYLIK qatorlarini bir martada to‘lash (kunlik emas)."""
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

    for emp in _monthly_employees(tenant):
        ensure_payroll_item(tenant, emp, year=year, month=month)

    period.refresh_from_db()
    paid = 0
    for item in period.items.select_related("employee").filter(work_date__isnull=True):
        if SalaryPayment.objects.filter(item=item).exists():
            continue
        if not item.employee.is_active or item.employee.is_daily:
            continue
        mark_item_paid(item, method=method)
        paid += 1
    return paid
