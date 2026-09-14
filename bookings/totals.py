"""Tanlangan davr bo‘yicha bronlar jami (bazaviy valyutada)."""

from calendar import monthrange
from datetime import date
from decimal import Decimal

from core.currency import to_base_amount
from core.dates import parse_user_date

from .models import Reservation

VALUE_STATUSES = (
    Reservation.Status.CONFIRMED,
    Reservation.Status.CHECKED_IN,
    Reservation.Status.CHECKED_OUT,
)


def parse_iso_date(value: str | None) -> date | None:
    """ISO yoki 13.09.2026 — yil 0/0002 qabul qilinmaydi."""
    return parse_user_date(value)


def default_month_bounds(day: date) -> tuple[date, date]:
    start = day.replace(day=1)
    end = day.replace(day=monthrange(day.year, day.month)[1])
    return start, end


def normalize_period(start: date | None, end: date | None) -> tuple[date | None, date | None]:
    if start and end and end < start:
        return end, start
    return start, end


def reservations_in_period(qs, start: date | None, end: date | None):
    """Stay overlap on [start, end] inclusive. Checkout day is not a night."""
    start, end = normalize_period(start, end)
    if start:
        qs = qs.filter(check_out__gt=start)
    if end:
        qs = qs.filter(check_in__lte=end)
    return qs


def value_reservations(qs, *, status: str = ""):
    """Real booking value: confirmed / in-house / checked-out, unless a status is chosen."""
    if status:
        return qs
    return qs.filter(status__in=VALUE_STATUSES)


def sum_reservation_totals(tenant, qs) -> Decimal:
    total = Decimal("0")
    for amount, currency, on_date in qs.values_list("total_amount", "currency", "check_in"):
        _, _, base = to_base_amount(
            tenant, amount or Decimal("0"), currency, on_date=on_date
        )
        total += base
    return total


def period_booking_summary(tenant, qs, *, status: str = "") -> dict:
    value_qs = value_reservations(qs, status=status)
    return {
        "total": sum_reservation_totals(tenant, value_qs),
        "count": value_qs.count(),
    }
