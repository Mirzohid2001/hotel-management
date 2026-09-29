"""Mobile parity gaps — minibar tez, bronlar list, dashboard, kassa tarixi, xizmat buyurtma."""

from calendar import monthrange
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from bookings.models import Reservation
from bookings.totals import (
    default_month_bounds,
    period_booking_summary,
    reservations_in_period,
)
from core.roles import CASH, DASHBOARD, FLOOR_VIEW, INVENTORY, SERVICES
from folio.models import CashShift
from properties.models import Room

from .auth import api_login_required, api_role_required, json_error, json_ok, parse_json
from .ops import _jsonable
from .views import _base_reservations, _reservation_summary, _shift_payload


def _parse_day(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw.strip())
    except ValueError:
        return None


def _in_house_by_room(request, room_number: str):
    number = (room_number or "").strip()
    if not number:
        return None, json_error("room_number required.")
    hotel = getattr(request, "active_property", None)
    room_qs = Room.objects.filter(
        tenant=request.tenant, number__iexact=number, is_active=True
    )
    if hotel is not None:
        room_qs = room_qs.filter(property=hotel)
    room = room_qs.first()
    if room is None:
        return None, json_error("Xona topilmadi.", status=404)
    reservation = (
        _base_reservations(request)
        .filter(room=room, status=Reservation.Status.CHECKED_IN)
        .select_related("guest", "room", "folio")
        .first()
    )
    if reservation is None:
        return None, json_error("Bu xonada yashovchi mehmon yo‘q.", status=400)
    return reservation, None


@api_login_required
@api_role_required(*INVENTORY)
@require_POST
def minibar_quick(request):
    """POST {room_number, item_id, quantity?} — web inventory:minibar_quick."""
    data = parse_json(request)
    reservation, err = _in_house_by_room(request, data.get("room_number") or "")
    if err is not None:
        return err
    item_id = data.get("item_id")
    if not item_id:
        return json_error("item_id required.")
    try:
        quantity = Decimal(str(data.get("quantity") or "1").replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return json_error("Invalid quantity.")
    if quantity <= 0:
        return json_error("quantity must be positive.")

    from inventory.models import StockItem
    from inventory.services import sell_minibar

    item = StockItem.objects.filter(
        pk=item_id, tenant=request.tenant, is_active=True, is_minibar=True
    ).first()
    if item is None:
        return json_error("Minibar item not found.", status=404)
    try:
        sale = sell_minibar(
            reservation=reservation,
            item=item,
            user=request.user,
            quantity=quantity,
        )
        balance = None
        try:
            balance = str(reservation.folio.balance)
        except Exception:
            pass
        return json_ok(
            {
                "sale_id": sale.pk,
                "room": reservation.room.number if reservation.room_id else "",
                "guest": reservation.guest.full_name if reservation.guest_id else "",
                "item": item.name,
                "quantity": str(sale.quantity),
                "amount": str(sale.quantity * sale.unit_price),
                "balance": balance,
                "reservation_id": reservation.pk,
            },
            status=201,
        )
    except ValidationError as exc:
        return json_error(
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
            status=400,
        )


@api_login_required
@api_role_required(*FLOOR_VIEW)
@require_GET
def reservations_list(request):
    """Period list — mirrors bookings.views.reservation_list filters."""
    today = timezone.localdate()
    if "date_from" in request.GET or "date_to" in request.GET:
        date_from = _parse_day(request.GET.get("date_from"))
        date_to = _parse_day(request.GET.get("date_to"))
        if request.GET.get("date_from") and date_from is None:
            return json_error("Invalid date_from.")
        if request.GET.get("date_to") and date_to is None:
            return json_error("Invalid date_to.")
    else:
        date_from, date_to = default_month_bounds(today)

    status = (request.GET.get("status") or "").strip()
    q = (request.GET.get("q") or "").strip()
    qs = _base_reservations(request)
    qs = reservations_in_period(qs, date_from, date_to)
    if status:
        if status not in dict(Reservation.Status.choices):
            return json_error("Invalid status.")
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(code__icontains=q)
            | Q(guest__first_name__icontains=q)
            | Q(guest__last_name__icontains=q)
            | Q(guest__phone__icontains=q)
            | Q(room__number__icontains=q)
        ).distinct()
    qs = qs.order_by("-check_in", "-pk")
    filter_count = qs.count()
    period_sum = period_booking_summary(request.tenant, qs, status=status)
    base = _base_reservations(request)
    items = [_reservation_summary(r) for r in qs[:200]]
    return json_ok(
        {
            "date_from": date_from.isoformat() if date_from else "",
            "date_to": date_to.isoformat() if date_to else "",
            "status": status,
            "q": q,
            "filter_count": filter_count,
            "booking_total": str(period_sum["total"]),
            "booking_total_count": period_sum["count"],
            "checked_in_count": base.filter(
                status=Reservation.Status.CHECKED_IN
            ).count(),
            "confirmed_count": base.filter(
                status=Reservation.Status.CONFIRMED
            ).count(),
            "arrivals_today": base.filter(
                check_in=today,
                status__in=[
                    Reservation.Status.CONFIRMED,
                    Reservation.Status.CHECKED_IN,
                ],
            ).count(),
            "statuses": [
                {"id": c[0], "label": str(c[1])} for c in Reservation.Status.choices
            ],
            "items": items,
        }
    )


@api_login_required
@api_role_required(*CASH)
@require_GET
def cash_shift_history(request):
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    qs = CashShift.objects.filter(tenant=request.tenant, hotel=hotel).select_related(
        "opened_by", "closed_by"
    )
    items = []
    for s in qs.order_by("-opened_at")[:40]:
        row = _shift_payload(s)
        row["is_open"] = s.closed_at is None
        items.append(row)
    return json_ok({"items": items})


@api_login_required
@api_role_required(*DASHBOARD)
@require_GET
def dashboard_report(request):
    from reports.accounting import build_daily_flash
    from reports.operations import dashboard_insights, operations_kpis

    day = timezone.localdate()
    day_s = (request.GET.get("date") or "").strip()
    if day_s:
        parsed = _parse_day(day_s)
        if parsed is None:
            return json_error("Invalid date.")
        day = parsed
    hotel = getattr(request, "active_property", None)
    flash = build_daily_flash(request.tenant, day, hotel=hotel)
    kpis = operations_kpis(request.tenant, day, hotel=hotel)
    insights = dashboard_insights(request.tenant, day, hotel=hotel)
    return json_ok(
        {
            "day": day.isoformat(),
            "flash": _jsonable(flash),
            "kpis": _jsonable(kpis),
            "insights": _jsonable(insights),
        }
    )


MONTH_LABELS = (
    "",
    "Yanvar",
    "Fevral",
    "Mart",
    "Aprel",
    "May",
    "Iyun",
    "Iyul",
    "Avgust",
    "Sentabr",
    "Oktabr",
    "Noyabr",
    "Dekabr",
)


@api_login_required
@api_role_required(*DASHBOARD)
@require_GET
def report_history(request):
    """Year/month index — mirrors reports:history links for mobile hub."""
    from finance.models import ProfitPeriod

    today = timezone.localdate()
    try:
        year = int(request.GET.get("year") or today.year)
    except (TypeError, ValueError):
        return json_error("Invalid year.")
    years = list(range(today.year, today.year - 6, -1))
    if year not in years:
        years.insert(0, year)
    months = []
    for num in range(1, 13):
        last = monthrange(year, num)[1]
        flash_day = date(year, num, last)
        if year == today.year and num == today.month:
            flash_day = today
        elif date(year, num, 1) > today:
            continue
        months.append(
            {
                "num": num,
                "label": MONTH_LABELS[num],
                "flash_day": flash_day.isoformat(),
                "year": year,
                "month": num,
            }
        )
    profit_periods = [
        {
            "id": p.pk,
            "started_on": p.started_on.isoformat() if p.started_on else None,
            "ended_on": p.ended_on.isoformat() if p.ended_on else None,
            "label": f"{p.started_on:%d.%m.%Y} — {p.ended_on:%d.%m.%Y}"
            if p.started_on and p.ended_on
            else str(p.pk),
        }
        for p in ProfitPeriod.objects.filter(
            tenant=request.tenant,
            ended_on__isnull=False,
            started_on__year=year,
        ).order_by("-started_on")[:40]
    ]
    return json_ok(
        {
            "year": year,
            "years": years,
            "months": months,
            "profit_periods": profit_periods,
        }
    )


@api_login_required
@api_role_required(*SERVICES)
@require_POST
def service_order_quick(request):
    """POST {room_number|reservation_id, service_id, quantity?, note?}."""
    data = parse_json(request)
    reservation = None
    rid = data.get("reservation_id")
    if rid not in (None, ""):
        try:
            rid = int(rid)
        except (TypeError, ValueError):
            return json_error("Invalid reservation_id.")
        reservation = _base_reservations(request).filter(pk=rid).first()
        if reservation is None:
            return json_error("Reservation not found.", status=404)
        if reservation.status != Reservation.Status.CHECKED_IN:
            return json_error("Mehmon in-house bo‘lishi kerak.", status=400)
    else:
        reservation, err = _in_house_by_room(request, data.get("room_number") or "")
        if err is not None:
            return err

    service_id = data.get("service_id")
    if not service_id:
        return json_error("service_id required.")
    try:
        quantity = Decimal(str(data.get("quantity") or "1").replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return json_error("Invalid quantity.")
    if quantity <= 0:
        return json_error("quantity must be positive.")

    from services.models import ServiceItem
    from services.services import order_service

    service = ServiceItem.objects.filter(
        pk=service_id, tenant=request.tenant, is_active=True
    ).first()
    if service is None:
        return json_error("Service not found.", status=404)
    try:
        order = order_service(
            reservation=reservation,
            service=service,
            user=request.user,
            quantity=quantity,
            note=(data.get("note") or "").strip(),
        )
        balance = None
        try:
            balance = str(reservation.folio.balance)
        except Exception:
            pass
        return json_ok(
            {
                "order_id": order.pk,
                "service": service.name,
                "quantity": str(order.quantity),
                "amount": str(order.amount),
                "balance": balance,
                "reservation_id": reservation.pk,
                "room": reservation.room.number if reservation.room_id else "",
            },
            status=201,
        )
    except ValidationError as exc:
        return json_error(
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
            status=400,
        )


@api_login_required
@api_role_required(*SERVICES)
@require_GET
def service_orders_recent(request):
    from services.models import ServiceOrder

    hotel = getattr(request, "active_property", None)
    qs = ServiceOrder.objects.filter(tenant=request.tenant).select_related(
        "service", "reservation", "reservation__room", "reservation__guest"
    )
    if hotel is not None:
        qs = qs.filter(reservation__hotel=hotel)
    items = [
        {
            "id": o.pk,
            "service": o.service.name if o.service_id else "",
            "quantity": str(o.quantity),
            "amount": str(o.amount),
            "room": o.reservation.room.number
            if o.reservation_id and o.reservation.room_id
            else "",
            "guest": o.reservation.guest.full_name
            if o.reservation_id and o.reservation.guest_id
            else "",
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "reservation_id": o.reservation_id,
        }
        for o in qs.order_by("-created_at")[:50]
    ]
    return json_ok({"items": items})
