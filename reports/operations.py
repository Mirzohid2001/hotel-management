"""Operational analytics for dashboard / management."""

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from bookings.models import Reservation
from finance.models import Expense
from folio.models import Folio, GuestPayment
from housekeeping.models import HousekeepingTask
from maintenance.models import MaintenanceTicket
from properties.models import Room

from .services import adr_revpar, occupancy_stats, revenue_on


def room_status_summary(tenant, *, hotel=None) -> list[dict]:
    rooms = Room.objects.filter(tenant=tenant, is_active=True)
    if hotel is not None:
        rooms = rooms.filter(property=hotel)
    counts = {row["status"]: row["c"] for row in rooms.values("status").annotate(c=Count("id"))}
    labels = dict(Room.Status.choices)
    return [
        {
            "status": status,
            "label": labels.get(status, status),
            "count": counts.get(status, 0),
        }
        for status, _ in Room.Status.choices
    ]


def revenue_trend(tenant, end_day: date, *, days: int = 7, hotel=None) -> list[dict]:
    start = end_day - timedelta(days=days - 1)
    qs = GuestPayment.objects.filter(
        tenant=tenant,
        is_void=False,
        created_at__date__gte=start,
        created_at__date__lte=end_day,
    )
    if hotel is not None:
        qs = qs.filter(folio__reservation__hotel=hotel)
    by_day = {
        row["created_at__date"]: row["total"] or Decimal("0")
        for row in qs.values("created_at__date").annotate(total=Sum("amount_base"))
    }
    peak = max(by_day.values(), default=Decimal("0"))
    rows = []
    for i in range(days):
        d = start + timedelta(days=i)
        amount = by_day.get(d, Decimal("0"))
        pct = int((amount / peak * 100)) if peak > 0 else 0
        rows.append(
            {
                "day": d,
                "label": d.strftime("%d.%m"),
                "amount": amount,
                "bar_pct": max(pct, 4 if amount > 0 else 0),
                "is_today": d == end_day,
            }
        )
    return rows


def operations_kpis(tenant, day: date, *, hotel=None) -> dict:
    rooms = Room.objects.filter(tenant=tenant, is_active=True)
    reservations = Reservation.objects.filter(tenant=tenant)
    folios = Folio.objects.filter(tenant=tenant, is_open=True)
    hk = HousekeepingTask.objects.filter(
        tenant=tenant,
        status__in=[HousekeepingTask.Status.PENDING, HousekeepingTask.Status.IN_PROGRESS],
    )
    maintenance = MaintenanceTicket.objects.filter(
        tenant=tenant,
        status__in=[MaintenanceTicket.Status.OPEN, MaintenanceTicket.Status.IN_PROGRESS],
    )

    if hotel is not None:
        rooms = rooms.filter(property=hotel)
        reservations = reservations.filter(hotel=hotel)
        folios = folios.filter(reservation__hotel=hotel)
        hk = hk.filter(room__property=hotel)
        maintenance = maintenance.filter(room__property=hotel)

    open_folio_balance = Decimal("0")
    open_folio_count = 0
    for folio in folios.prefetch_related("charges", "payments"):
        bal = folio.balance
        if bal > 0:
            open_folio_count += 1
            open_folio_balance += bal

    return {
        "dirty_rooms": rooms.filter(status=Room.Status.DIRTY).count(),
        "cleaning_rooms": rooms.filter(status=Room.Status.CLEANING).count(),
        "ooo_rooms": rooms.filter(status=Room.Status.OUT_OF_ORDER).count(),
        "ready_rooms": rooms.filter(status=Room.Status.READY).count(),
        "inquiries": reservations.filter(status=Reservation.Status.INQUIRY).count(),
        "confirmed_arrivals_tomorrow": reservations.filter(
            check_in=day + timedelta(days=1),
            status=Reservation.Status.CONFIRMED,
        ).count(),
        "hk_tasks": hk.count(),
        "maintenance_open": maintenance.count(),
        "open_folio_count": open_folio_count,
        "open_folio_balance": open_folio_balance,
        "expenses_pending": Expense.objects.filter(
            tenant=tenant, status=Expense.Status.DRAFT, **({"hotel": hotel} if hotel else {})
        ).count(),
    }


def dashboard_insights(tenant, day: date, *, hotel=None) -> dict:
    today_stats = adr_revpar(tenant, day, hotel=hotel)
    yesterday = day - timedelta(days=1)
    y_stats = adr_revpar(tenant, yesterday, hotel=hotel)
    today_rev = revenue_on(tenant, day, hotel=hotel)
    y_rev = revenue_on(tenant, yesterday, hotel=hotel)

    def delta(cur, prev):
        if prev and prev != 0:
            return ((cur - prev) / prev * 100).quantize(Decimal("0.1"))
        return None

    return {
        "occupancy_delta": delta(today_stats["occupancy_percent"], y_stats["occupancy_percent"]),
        "revenue_delta": delta(today_rev, y_rev),
        "adr_delta": delta(today_stats["adr"], y_stats["adr"]),
        "yesterday_revenue": y_rev,
        "yesterday_occupancy": y_stats["occupancy_percent"],
    }
