"""Financial reports for hotel accounting / hisob-kitob."""

from datetime import date
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils.translation import gettext as _

from finance.models import Expense
from folio.city_ledger import ar_aging
from folio.models import CompanyPayment, Folio, FolioCharge, GuestPayment
from folio.services import EMEHMON_LEGACY_MARKERS
from hr.models import SalaryAdvance, SalaryPayment

from .services import adr_revpar, charges_on, payroll_in_month, pnl_lite, revenue_on


def _emehmon_payment_q() -> Q:
    """Mehmondan olingan E-mehmon to‘lovlari (o‘tkinchi, tushum emas)."""
    q = Q()
    for marker in EMEHMON_LEGACY_MARKERS:
        q |= Q(note__icontains=marker)
    return q


def revenue_by_charge_type(tenant, year: int, month: int, *, hotel=None) -> dict:
    qs = FolioCharge.objects.filter(
        tenant=tenant,
        is_void=False,
        created_at__year=year,
        created_at__month=month,
    ).exclude(charge_type=FolioCharge.ChargeType.EMEHMON)
    if hotel is not None:
        qs = qs.filter(folio__reservation__hotel=hotel)
    rows = qs.values("charge_type").annotate(total=Sum("amount_base")).order_by("charge_type")
    breakdown = []
    total = Decimal("0")
    labels = dict(FolioCharge.ChargeType.choices)
    for row in rows:
        amt = row["total"] or Decimal("0")
        total += amt
        breakdown.append(
            {
                "key": row["charge_type"],
                "label": labels.get(row["charge_type"], row["charge_type"]),
                "amount": amt,
            }
        )
    return {"breakdown": breakdown, "total": total}


def _net_guest_payments(qs) -> Decimal:
    """Kirim to‘lovlari − sdachi/qaytarish."""
    from folio.models import GuestPayment

    incoming = (
        qs.exclude(kind=GuestPayment.Kind.REFUND).aggregate(s=Sum("amount_base"))["s"]
        or Decimal("0")
    )
    refunds = (
        qs.filter(kind=GuestPayment.Kind.REFUND).aggregate(s=Sum("amount_base"))["s"]
        or Decimal("0")
    )
    return incoming - refunds


def cash_revenue_in_range(tenant, start: date, end: date, *, hotel=None) -> dict:
    guest_qs = GuestPayment.objects.filter(
        tenant=tenant,
        is_void=False,
        created_at__date__gte=start,
        created_at__date__lte=end,
    ).exclude(_emehmon_payment_q())
    company_qs = CompanyPayment.objects.filter(
        tenant=tenant,
        is_void=False,
        created_at__date__gte=start,
        created_at__date__lte=end,
    )
    if hotel is not None:
        guest_qs = guest_qs.filter(folio__reservation__hotel=hotel)
        company_qs = company_qs.filter(invoice__hotel=hotel)
    guest = _net_guest_payments(guest_qs)
    company = company_qs.aggregate(s=Sum("amount_base"))["s"] or Decimal("0")
    return {
        "guest_payments": guest,
        "company_payments": company,
        "total": guest + company,
    }


def expenses_in_range(tenant, start: date, end: date, *, hotel=None) -> Decimal:
    qs = Expense.objects.filter(
        tenant=tenant,
        expense_date__gte=start,
        expense_date__lte=end,
        status__in=[Expense.Status.APPROVED, Expense.Status.PAID],
    )
    if hotel is not None:
        qs = qs.filter(hotel=hotel)
    return qs.aggregate(s=Sum("amount_base"))["s"] or Decimal("0")


def payroll_in_range(tenant, start: date, end: date) -> Decimal:
    return (
        SalaryPayment.objects.filter(
            tenant=tenant,
            paid_at__date__gte=start,
            paid_at__date__lte=end,
        ).aggregate(s=Sum("amount_base"))["s"]
        or Decimal("0")
    )


def cash_revenue_in_month(tenant, year: int, month: int, *, hotel=None) -> dict:
    guest_qs = GuestPayment.objects.filter(
        tenant=tenant,
        is_void=False,
        created_at__year=year,
        created_at__month=month,
    ).exclude(_emehmon_payment_q())
    company_qs = CompanyPayment.objects.filter(
        tenant=tenant,
        is_void=False,
        created_at__year=year,
        created_at__month=month,
    )
    if hotel is not None:
        guest_qs = guest_qs.filter(folio__reservation__hotel=hotel)
        company_qs = company_qs.filter(invoice__hotel=hotel)
    guest = _net_guest_payments(guest_qs)
    company = company_qs.aggregate(s=Sum("amount_base"))["s"] or Decimal("0")
    return {
        "guest_payments": guest,
        "company_payments": company,
        "total": guest + company,
    }


def expenses_by_category(tenant, year: int, month: int, *, hotel=None) -> dict:
    qs = Expense.objects.filter(
        tenant=tenant,
        expense_date__year=year,
        expense_date__month=month,
        status__in=[Expense.Status.APPROVED, Expense.Status.PAID],
    )
    if hotel is not None:
        qs = qs.filter(hotel=hotel)
    rows = (
        qs.values("category_id", "category__name")
        .annotate(total=Sum("amount_base"))
        .order_by("-total")
    )
    breakdown = []
    total = Decimal("0")
    for row in rows:
        amt = row["total"] or Decimal("0")
        total += amt
        breakdown.append({"label": row["category__name"], "amount": amt})
    return {"breakdown": breakdown, "total": total}


def advances_in_month(tenant, year: int, month: int) -> Decimal:
    return (
        SalaryAdvance.objects.filter(
            tenant=tenant,
            advance_date__year=year,
            advance_date__month=month,
        ).aggregate(s=Sum("amount_base"))["s"]
        or Decimal("0")
    )


def advances_in_range(tenant, start: date, end: date) -> Decimal:
    return (
        SalaryAdvance.objects.filter(
            tenant=tenant,
            advance_date__gte=start,
            advance_date__lte=end,
        ).aggregate(s=Sum("amount_base"))["s"]
        or Decimal("0")
    )


def commission_in_range(tenant, start: date, end: date, *, hotel=None) -> Decimal:
    """Checkout tushgan bronlar bo‘yicha hisoblangan yo‘naltiruvchi komissiyasi."""
    from bookings.commission import reservation_commission_amount
    from bookings.models import Reservation

    qs = (
        Reservation.objects.filter(
            tenant=tenant,
            referrer__isnull=False,
            check_out__gte=start,
            check_out__lte=end,
        )
        .exclude(
            status__in=[
                Reservation.Status.CANCELLED,
                Reservation.Status.NO_SHOW,
            ]
        )
        .select_related("folio")
        .prefetch_related("folio__charges")
    )
    if hotel is not None:
        qs = qs.filter(hotel=hotel)
    total = Decimal("0")
    for res in qs:
        total += reservation_commission_amount(res)
    return total


def commission_in_month(tenant, year: int, month: int, *, hotel=None) -> Decimal:
    from calendar import monthrange

    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return commission_in_range(tenant, start, end, hotel=hotel)


def inventory_cost_in_range(tenant, start: date, end: date, *, hotel=None) -> Decimal:
    """
    Ombor tannarxi (bazaviy valyuta): kirim × unit_cost, mahsulot valyutasi bo‘yicha.
    """
    from core.currency import to_base_amount
    from inventory.models import StockMovement

    total = Decimal("0")
    moves = StockMovement.objects.filter(
        tenant=tenant,
        movement_type=StockMovement.MovementType.IN,
        created_at__date__gte=start,
        created_at__date__lte=end,
    ).select_related("item")
    if hotel is not None:
        moves = moves.filter(item__hotel=hotel)
    for move in moves:
        line = Decimal(move.quantity) * Decimal(move.item.unit_cost or 0)
        _c, _r, base = to_base_amount(
            tenant,
            line,
            getattr(move.item, "currency", None) or tenant.currency,
            on_date=move.created_at.date() if move.created_at else start,
        )
        total += base
    return total.quantize(Decimal("0.01"))


def inventory_cost_in_month(tenant, year: int, month: int, *, hotel=None) -> Decimal:
    from calendar import monthrange

    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return inventory_cost_in_range(tenant, start, end, hotel=hotel)


def _operating_bundle(
    *,
    expenses: Decimal,
    payroll: Decimal,
    advances: Decimal,
    commission: Decimal,
    inventory: Decimal,
    emehmon_shortfall: Decimal = Decimal("0"),
) -> dict:
    labor = payroll + advances
    operating = expenses + labor + commission + inventory + emehmon_shortfall
    return {
        "expenses_total": expenses,
        "payroll": payroll,
        "advances": advances,
        "labor_total": labor,
        "commission": commission,
        "inventory_cost": inventory,
        "emehmon_shortfall": emehmon_shortfall,
        "operating_costs": operating,
    }


def cash_pnl_for_range(tenant, start: date, end: date, *, hotel=None) -> dict:
    """Naqd sof: tushum − rasxod − oylik − avans − komissiya − ombor − E-mehmon farq."""
    from bookings.emehmon import emehmon_shortfall_for_range

    rev = cash_revenue_in_range(tenant, start, end, hotel=hotel)
    costs = _operating_bundle(
        expenses=expenses_in_range(tenant, start, end, hotel=hotel),
        payroll=payroll_in_range(tenant, start, end),
        advances=advances_in_range(tenant, start, end),
        commission=commission_in_range(tenant, start, end, hotel=hotel),
        inventory=inventory_cost_in_range(tenant, start, end, hotel=hotel),
        emehmon_shortfall=emehmon_shortfall_for_range(
            tenant, start, end, hotel=hotel
        ),
    )
    return {
        "start": start,
        "end": end,
        "revenue_total": rev["total"],
        "guest_payments": rev["guest_payments"],
        "company_payments": rev["company_payments"],
        **costs,
        "net": rev["total"] - costs["operating_costs"],
    }


def build_pnl_report(tenant, year: int, month: int, *, basis="cash", hotel=None) -> dict:
    from calendar import monthrange

    from bookings.emehmon import emehmon_shortfall_for_range

    basis = basis if basis in {"cash", "accrual"} else "cash"
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    if basis == "accrual":
        rev = revenue_by_charge_type(tenant, year, month, hotel=hotel)
        revenue_total = rev["total"]
        revenue_breakdown = rev["breakdown"]
    else:
        rev = cash_revenue_in_month(tenant, year, month, hotel=hotel)
        revenue_total = rev["total"]
        revenue_breakdown = [
            {"label": _("Mehmon to‘lovlari"), "amount": rev["guest_payments"]},
            {"label": _("Kompaniya to‘lovlari"), "amount": rev["company_payments"]},
        ]

    exp = expenses_by_category(tenant, year, month, hotel=hotel)
    shortfall = emehmon_shortfall_for_range(tenant, start, end, hotel=hotel)
    costs = _operating_bundle(
        expenses=exp["total"],
        payroll=payroll_in_month(tenant, year, month),
        advances=advances_in_month(tenant, year, month),
        commission=commission_in_month(tenant, year, month, hotel=hotel),
        inventory=inventory_cost_in_month(tenant, year, month, hotel=hotel),
        emehmon_shortfall=shortfall,
    )
    cost_breakdown = list(exp["breakdown"])
    if costs["payroll"]:
        cost_breakdown.append({"label": _("Oylik to‘lovlar"), "amount": costs["payroll"]})
    if costs["advances"]:
        cost_breakdown.append({"label": _("Xodim avanslari"), "amount": costs["advances"]})
    if costs["commission"]:
        cost_breakdown.append(
            {"label": _("Yo‘naltiruvchi komissiya"), "amount": costs["commission"]}
        )
    if costs["inventory_cost"]:
        cost_breakdown.append(
            {"label": _("Ombor xarid (tannarx)"), "amount": costs["inventory_cost"]}
        )
    if costs["emehmon_shortfall"]:
        cost_breakdown.append(
            {
                "label": _("E-mehmon (qoplanmagan)"),
                "amount": costs["emehmon_shortfall"],
            }
        )

    return {
        "year": year,
        "month": month,
        "basis": basis,
        "revenue_total": revenue_total,
        "revenue_breakdown": revenue_breakdown,
        "expenses_breakdown": cost_breakdown,
        **costs,
        "net": revenue_total - costs["operating_costs"],
    }


def payment_method_breakdown(tenant, start: date, end: date, *, hotel=None) -> dict:
    guest_qs = GuestPayment.objects.filter(
        tenant=tenant,
        is_void=False,
        created_at__date__gte=start,
        created_at__date__lte=end,
    )
    company_qs = CompanyPayment.objects.filter(
        tenant=tenant,
        is_void=False,
        created_at__date__gte=start,
        created_at__date__lte=end,
    )
    expense_qs = Expense.objects.filter(
        tenant=tenant,
        expense_date__gte=start,
        expense_date__lte=end,
        status=Expense.Status.PAID,
    )
    payroll_qs = SalaryPayment.objects.filter(
        tenant=tenant,
        paid_at__date__gte=start,
        paid_at__date__lte=end,
    )
    if hotel is not None:
        guest_qs = guest_qs.filter(folio__reservation__hotel=hotel)
        company_qs = company_qs.filter(invoice__hotel=hotel)
        expense_qs = expense_qs.filter(hotel=hotel)

    methods = {}
    for label, choices in [
        ("guest_in", GuestPayment.Method.choices),
        ("company_in", GuestPayment.Method.choices),
        ("expense_out", Expense.PaymentMethod.choices),
        ("payroll_out", [("cash", "Cash"), ("transfer", "Transfer"), ("card", "Card")]),
    ]:
        for key, _ in choices:
            methods.setdefault(key, {"in": Decimal("0"), "out": Decimal("0")})

    for row in (
        guest_qs.exclude(kind=GuestPayment.Kind.REFUND)
        .values("method")
        .annotate(total=Sum("amount_base"))
    ):
        methods[row["method"]]["in"] += row["total"] or Decimal("0")
    for row in (
        guest_qs.filter(kind=GuestPayment.Kind.REFUND)
        .values("method")
        .annotate(total=Sum("amount_base"))
    ):
        methods[row["method"]]["out"] += row["total"] or Decimal("0")
    for row in company_qs.values("method").annotate(total=Sum("amount_base")):
        methods[row["method"]]["in"] += row["total"] or Decimal("0")
    for row in expense_qs.values("payment_method").annotate(total=Sum("amount_base")):
        methods[row["payment_method"]]["out"] += row["total"] or Decimal("0")
    for row in payroll_qs.values("method").annotate(total=Sum("amount_base")):
        methods[row["method"]]["out"] += row["total"] or Decimal("0")

    labels = dict(GuestPayment.Method.choices)
    rows = []
    total_in = Decimal("0")
    total_out = Decimal("0")
    for key, vals in methods.items():
        if vals["in"] == 0 and vals["out"] == 0:
            continue
        total_in += vals["in"]
        total_out += vals["out"]
        rows.append(
            {
                "method": key,
                "label": labels.get(key, key),
                "in": vals["in"],
                "out": vals["out"],
                "net": vals["in"] - vals["out"],
            }
        )
    rows.sort(key=lambda r: r["in"] + r["out"], reverse=True)
    return {"rows": rows, "total_in": total_in, "total_out": total_out, "net": total_in - total_out}


def guest_ar_summary(tenant, *, hotel=None) -> dict:
    folios = Folio.objects.filter(tenant=tenant, is_open=True).select_related(
        "reservation", "reservation__guest", "reservation__hotel"
    )
    if hotel is not None:
        folios = folios.filter(reservation__hotel=hotel)
    rows = []
    total = Decimal("0")
    for folio in folios:
        bal = folio.balance
        if bal <= 0:
            continue
        total += bal
        res = folio.reservation
        rows.append(
            {
                "code": res.code,
                "guest": res.guest.full_name,
                "balance": bal,
                "pk": res.pk,
            }
        )
    rows.sort(key=lambda r: r["balance"], reverse=True)
    return {"count": len(rows), "total": total, "rows": rows}


def build_daily_flash(tenant, day: date, *, hotel=None) -> dict:
    stats = adr_revpar(tenant, day, hotel=hotel)
    payments = payment_method_breakdown(tenant, day, day, hotel=hotel)
    guest_ar = guest_ar_summary(tenant, hotel=hotel)
    company_ar = ar_aging(tenant)
    mtd = pnl_lite(tenant, day.year, day.month, hotel=hotel)
    expenses_today = Expense.objects.filter(
        tenant=tenant,
        expense_date=day,
        status__in=[Expense.Status.APPROVED, Expense.Status.PAID],
    )
    if hotel is not None:
        expenses_today = expenses_today.filter(hotel=hotel)
    expenses_today = expenses_today.aggregate(s=Sum("amount_base"))["s"] or Decimal("0")
    return {
        "day": day,
        "stats": stats,
        "revenue_cash": revenue_on(tenant, day, hotel=hotel),
        "revenue_accrual": charges_on(tenant, day, hotel=hotel),
        "payments": payments,
        "guest_ar": guest_ar,
        "company_ar": company_ar,
        "mtd": mtd,
        "expenses_today": expenses_today,
    }
