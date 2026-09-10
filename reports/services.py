from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from bookings.models import Reservation
from finance.models import Expense
from folio.models import FolioCharge, GuestPayment
from hr.models import SalaryPayment
from properties.models import Room


def arrivals_on(tenant, day: date, *, hotel=None):
    qs = Reservation.objects.filter(
        tenant=tenant,
        check_in=day,
        status__in=[
            Reservation.Status.CONFIRMED,
            Reservation.Status.CHECKED_IN,
            Reservation.Status.INQUIRY,
        ],
    ).select_related("guest")
    if hotel is not None:
        qs = qs.filter(hotel=hotel)
    return qs


def departures_on(tenant, day: date, *, hotel=None):
    qs = Reservation.objects.filter(
        tenant=tenant,
        check_out=day,
        status__in=[
            Reservation.Status.CHECKED_IN,
            Reservation.Status.CHECKED_OUT,
            Reservation.Status.CONFIRMED,
        ],
    ).select_related("guest")
    if hotel is not None:
        qs = qs.filter(hotel=hotel)
    return qs


def in_house_on(tenant, day: date, *, hotel=None):
    qs = (
        Reservation.objects.filter(tenant=tenant)
        .overlapping(day, day + timedelta(days=1))
        .filter(status=Reservation.Status.CHECKED_IN)
        .select_related("guest", "room")
    )
    if hotel is not None:
        qs = qs.filter(hotel=hotel)
    return qs


def occupancy_stats(tenant, day: date, *, hotel=None) -> dict:
    rooms = Room.objects.filter(tenant=tenant, is_active=True).exclude(
        status=Room.Status.OUT_OF_ORDER
    )
    if hotel is not None:
        rooms = rooms.filter(property=hotel)
    total_rooms = rooms.count()
    occupied_qs = (
        Reservation.objects.filter(tenant=tenant)
        .overlapping(day, day + timedelta(days=1))
        .exclude(
            status__in=[
                Reservation.Status.CANCELLED,
                Reservation.Status.NO_SHOW,
                Reservation.Status.CHECKED_OUT,
            ]
        )
        .filter(room__isnull=False)
    )
    if hotel is not None:
        occupied_qs = occupied_qs.filter(hotel=hotel)
    occupied = occupied_qs.values("room_id").distinct().count()
    rate = (Decimal(occupied) / Decimal(total_rooms) * 100) if total_rooms else Decimal("0")
    return {
        "total_rooms": total_rooms,
        "occupied_rooms": occupied,
        "occupancy_percent": rate.quantize(Decimal("0.01")),
    }


def revenue_on(tenant, day: date, *, hotel=None) -> Decimal:
    from folio.models import GuestPayment

    qs = GuestPayment.objects.filter(tenant=tenant, created_at__date=day, is_void=False)
    if hotel is not None:
        qs = qs.filter(folio__reservation__hotel=hotel)
    incoming = (
        qs.exclude(kind=GuestPayment.Kind.REFUND).aggregate(s=Sum("amount_base"))["s"]
        or Decimal("0")
    )
    refunds = (
        qs.filter(kind=GuestPayment.Kind.REFUND).aggregate(s=Sum("amount_base"))["s"]
        or Decimal("0")
    )
    return incoming - refunds


def charges_on(tenant, day: date, *, hotel=None) -> Decimal:
    qs = FolioCharge.objects.filter(
        tenant=tenant, created_at__date=day, is_void=False
    )
    if hotel is not None:
        qs = qs.filter(folio__reservation__hotel=hotel)
    return qs.aggregate(s=Sum("amount_base"))["s"] or Decimal("0")


def expenses_in_month(tenant, year: int, month: int, *, hotel=None) -> Decimal:
    qs = Expense.objects.filter(
        tenant=tenant,
        expense_date__year=year,
        expense_date__month=month,
        status__in=[Expense.Status.APPROVED, Expense.Status.PAID],
    )
    if hotel is not None:
        qs = qs.filter(hotel=hotel)
    return qs.aggregate(s=Sum("amount_base"))["s"] or Decimal("0")


def payroll_in_month(tenant, year: int, month: int) -> Decimal:
    return (
        SalaryPayment.objects.filter(
            tenant=tenant, paid_at__year=year, paid_at__month=month
        ).aggregate(s=Sum("amount_base"))["s"]
        or Decimal("0")
    )


def pnl_lite(tenant, year: int, month: int, *, hotel=None) -> dict:
    """Month-to-date cash net — aligned with full P&L cash basis."""
    from calendar import monthrange

    from reports.accounting import cash_pnl_for_range

    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    today = timezone.localdate()
    if end > today:
        end = today
    if end < start:
        end = start
    pnl = cash_pnl_for_range(tenant, start, end, hotel=hotel)
    return {
        "revenue": pnl["revenue_total"],
        "expenses": pnl["expenses_total"],
        "payroll": pnl["payroll"],
        "advances": pnl["advances"],
        "commission": pnl["commission"],
        "inventory_cost": pnl["inventory_cost"],
        "emehmon_shortfall": pnl.get("emehmon_shortfall") or Decimal("0"),
        "labor_total": pnl["labor_total"],
        "operating_costs": pnl["operating_costs"],
        "net": pnl["net"],
    }


def adr_revpar(tenant, day: date, *, hotel=None) -> dict:
    occ = occupancy_stats(tenant, day, hotel=hotel)
    room_charges = FolioCharge.objects.filter(
        tenant=tenant,
        created_at__date=day,
        charge_type=FolioCharge.ChargeType.ROOM,
        is_void=False,
    )
    if hotel is not None:
        room_charges = room_charges.filter(folio__reservation__hotel=hotel)
    room_revenue = room_charges.aggregate(s=Sum("amount_base"))["s"] or Decimal("0")
    occupied = occ["occupied_rooms"] or 0
    total = occ["total_rooms"] or 0
    adr = (room_revenue / Decimal(occupied)) if occupied else Decimal("0")
    revpar = (room_revenue / Decimal(total)) if total else Decimal("0")
    return {
        "room_revenue": room_revenue,
        "adr": adr.quantize(Decimal("0.01")),
        "revpar": revpar.quantize(Decimal("0.01")),
        **occ,
    }
