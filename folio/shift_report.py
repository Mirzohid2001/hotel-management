from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from finance.models import Expense
from folio.models import CashShiftMovement, GuestPayment
from hr.models import SalaryPayment

from .models import CashShift


def _shift_window(shift: CashShift):
    end = shift.closed_at or timezone.now()
    return shift.opened_at, end


def movements_in_shift(shift: CashShift) -> dict:
    qs = CashShiftMovement.objects.filter(
        tenant=shift.tenant, shift=shift
    ).select_related("created_by")
    pay_in = (
        qs.filter(kind=CashShiftMovement.Kind.PAY_IN).aggregate(s=Sum("amount_base"))["s"]
        or Decimal("0")
    )
    pay_out = (
        qs.filter(kind=CashShiftMovement.Kind.PAY_OUT).aggregate(s=Sum("amount_base"))["s"]
        or Decimal("0")
    )
    return {
        "pay_in": pay_in,
        "pay_out": pay_out,
        "net": pay_in - pay_out,
        "rows": list(qs.order_by("-created_at")[:40]),
    }


def cash_out_in_shift(shift: CashShift) -> dict:
    start, end = _shift_window(shift)
    expense_qs = Expense.objects.filter(
        tenant=shift.tenant,
        status=Expense.Status.PAID,
        payment_method=Expense.PaymentMethod.CASH,
        paid_at__gte=start,
        paid_at__lte=end,
    )
    if shift.hotel_id:
        expense_qs = expense_qs.filter(hotel_id=shift.hotel_id)
    payroll_qs = SalaryPayment.objects.filter(
        tenant=shift.tenant,
        method="cash",
        paid_at__gte=start,
        paid_at__lte=end,
    )
    expense_total = expense_qs.aggregate(s=Sum("amount_base"))["s"] or Decimal("0")
    payroll_total = payroll_qs.aggregate(s=Sum("amount_base"))["s"] or Decimal("0")
    return {
        "expenses": expense_total,
        "payroll": payroll_total,
        "total": expense_total + payroll_total,
        "expense_rows": list(expense_qs.order_by("-paid_at")[:20]),
        "payroll_rows": list(payroll_qs.select_related("item__employee").order_by("-paid_at")[:20]),
    }


def payments_in_shift(shift: CashShift) -> dict:
    start, end = _shift_window(shift)
    bound_cash = GuestPayment.objects.filter(
        tenant=shift.tenant,
        cash_shift=shift,
        method=GuestPayment.Method.CASH,
        is_void=False,
    ).select_related("folio__reservation", "folio__reservation__guest")
    legacy_cash = GuestPayment.objects.filter(
        tenant=shift.tenant,
        method=GuestPayment.Method.CASH,
        cash_shift__isnull=True,
        is_void=False,
        created_at__gte=start,
        created_at__lte=end,
    ).select_related("folio__reservation", "folio__reservation__guest")
    card = GuestPayment.objects.filter(
        tenant=shift.tenant,
        method=GuestPayment.Method.CARD,
        is_void=False,
        created_at__gte=start,
        created_at__lte=end,
    ).select_related("folio__reservation", "folio__reservation__guest")
    transfer = GuestPayment.objects.filter(
        tenant=shift.tenant,
        method=GuestPayment.Method.TRANSFER,
        is_void=False,
        created_at__gte=start,
        created_at__lte=end,
    ).select_related("folio__reservation", "folio__reservation__guest")
    if shift.hotel_id:
        hotel_q = {"folio__reservation__hotel_id": shift.hotel_id}
        legacy_cash = legacy_cash.filter(**hotel_q)
        card = card.filter(**hotel_q)
        transfer = transfer.filter(**hotel_q)

    cash_in = (bound_cash.exclude(kind=GuestPayment.Kind.REFUND).aggregate(s=Sum("amount_base"))["s"] or Decimal("0")) + (
        legacy_cash.exclude(kind=GuestPayment.Kind.REFUND).aggregate(s=Sum("amount_base"))["s"] or Decimal("0")
    )
    cash_refund = (
        bound_cash.filter(kind=GuestPayment.Kind.REFUND).aggregate(s=Sum("amount_base"))["s"]
        or Decimal("0")
    ) + (
        legacy_cash.filter(kind=GuestPayment.Kind.REFUND).aggregate(s=Sum("amount_base"))["s"]
        or Decimal("0")
    )
    card_total = (
        card.exclude(kind=GuestPayment.Kind.REFUND).aggregate(s=Sum("amount_base"))["s"]
        or Decimal("0")
    ) - (
        card.filter(kind=GuestPayment.Kind.REFUND).aggregate(s=Sum("amount_base"))["s"]
        or Decimal("0")
    )
    transfer_total = (
        transfer.exclude(kind=GuestPayment.Kind.REFUND).aggregate(s=Sum("amount_base"))["s"]
        or Decimal("0")
    ) - (
        transfer.filter(kind=GuestPayment.Kind.REFUND).aggregate(s=Sum("amount_base"))["s"]
        or Decimal("0")
    )

    rows = list(bound_cash.order_by("created_at")) + list(legacy_cash.order_by("created_at"))

    return {
        "cash_in": cash_in - cash_refund,
        "cash_refund": cash_refund,
        "card_total": card_total,
        "transfer_total": transfer_total,
        "non_cash_total": card_total + transfer_total,
        "rows": rows,
        "card_rows": list(card.order_by("-created_at")[:20]),
        "transfer_rows": list(transfer.order_by("-created_at")[:20]),
    }


def build_shift_report(shift: CashShift) -> dict:
    payments = payments_in_shift(shift)
    cash_out = cash_out_in_shift(shift)
    movements = movements_in_shift(shift)
    expected = (
        shift.opening_float
        + payments["cash_in"]
        + movements["pay_in"]
        - cash_out["total"]
        - movements["pay_out"]
    )
    return {
        "shift": shift,
        "payments": payments,
        "cash_out": cash_out,
        "movements": movements,
        "expected_cash": expected,
        "formula_label": _(
            "Boshlang‘ich + naqd kirim + kassa kirim − rasxod/oylik − kassa chiqim"
        ),
    }
