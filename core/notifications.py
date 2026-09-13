"""In-app operational alerts for the topbar."""

from urllib.parse import urlparse

from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from bookings.models import Reservation
from folio.models import Folio
from maintenance.models import MaintenanceTicket

SESSION_KEY = "dismissed_notify"


def notification_entry(*, kind, title, detail, url_name, pk=None, object_id=None):
    oid = object_id if object_id is not None else pk
    if pk is not None and url_name in {"bookings:detail", "folio:detail"}:
        url = reverse(url_name, args=[pk])
    else:
        url = reverse(url_name)
    return {
        "kind": kind,
        "title": title,
        "detail": detail,
        "url_name": url_name,
        "pk": pk,
        "url": url,
        "key": f"{kind}:{oid}",
    }


def dismissed_keys(request) -> set[str]:
    if request is None or not hasattr(request, "session"):
        return set()
    today = timezone.localdate().isoformat()
    data = request.session.get(SESSION_KEY) or {}
    return set(data.get(today) or [])


def dismiss_notification(request, key: str) -> None:
    key = (key or "").strip()
    if not key or request is None:
        return
    today = timezone.localdate().isoformat()
    data = request.session.get(SESSION_KEY) or {}
    day_keys = [k for k in (data.get(today) or []) if k]
    if key not in day_keys:
        day_keys.append(key)
    request.session[SESSION_KEY] = {today: day_keys}


def safe_next_url(value: str | None, fallback: str = "/", *, allowed_host: str | None = None) -> str:
    value = (value or "").strip()
    if not value:
        return fallback
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        host = (allowed_host or "").split(":")[0]
        incoming = parsed.netloc.split(":")[0]
        if not host or incoming != host:
            return fallback
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        value = path
    if not value.startswith("/") or value.startswith("//"):
        return fallback
    return value


def build_notifications(tenant, hotel=None, dismissed=None):
    if tenant is None:
        return {"items": [], "count": 0}

    today = timezone.localdate()
    items = []
    dismissed = set(dismissed or ())

    web_bookings = Reservation.objects.filter(
        tenant=tenant,
        source=Reservation.Source.WEBSITE,
        status__in=[Reservation.Status.INQUIRY, Reservation.Status.CONFIRMED],
    ).select_related("guest", "room")
    if hotel is not None:
        web_bookings = web_bookings.filter(hotel=hotel)
    for r in web_bookings.order_by("-created_at")[:6]:
        items.append(
            notification_entry(
                kind="web_booking",
                title=_("Veb-bron · %(code)s") % {"code": r.code},
                detail=f"{r.guest.full_name} · {r.get_status_display()}",
                url_name="bookings:detail",
                pk=r.pk,
            )
        )

    arrivals = Reservation.objects.filter(
        tenant=tenant,
        check_in=today,
        status__in=[Reservation.Status.CONFIRMED, Reservation.Status.INQUIRY],
    ).select_related("guest", "room")
    if hotel is not None:
        arrivals = arrivals.filter(hotel=hotel)
    for r in arrivals.order_by("check_in")[:8]:
        items.append(
            notification_entry(
                kind="arrival",
                title=_("Kelish · %(code)s") % {"code": r.code},
                detail=f"{r.guest.full_name}"
                + (f" · {r.room.number}" if r.room_id else ""),
                url_name="bookings:detail",
                pk=r.pk,
            )
        )

    departures = Reservation.objects.filter(
        tenant=tenant,
        check_out=today,
        status=Reservation.Status.CHECKED_IN,
    ).select_related("guest", "room")
    if hotel is not None:
        departures = departures.filter(hotel=hotel)
    for r in departures.order_by("check_out")[:8]:
        items.append(
            notification_entry(
                kind="departure",
                title=_("Ketish · %(code)s") % {"code": r.code},
                detail=f"{r.guest.full_name}"
                + (f" · {r.room.number}" if r.room_id else ""),
                url_name="bookings:detail",
                pk=r.pk,
            )
        )

    # Debt alerts: unpaid after stay ended (checked out / cancel / no-show),
    # or departure-day in-house still owing — NOT mid-stay balances.
    overdue = Folio.objects.filter(tenant=tenant, is_open=True).select_related(
        "reservation", "reservation__guest", "reservation__hotel"
    )
    if hotel is not None:
        overdue = overdue.filter(reservation__hotel=hotel)
    for folio in overdue.order_by("-opened_at")[:40]:
        if folio.balance <= 0:
            continue
        res = folio.reservation
        is_closed_status = res.status in {
            Reservation.Status.CHECKED_OUT,
            Reservation.Status.CANCELLED,
            Reservation.Status.NO_SHOW,
        }
        is_departure_day_owing = (
            res.status == Reservation.Status.CHECKED_IN and res.check_out <= today
        )
        if not (is_closed_status or is_departure_day_owing):
            continue
        items.append(
            notification_entry(
                kind="overdue",
                title=_("Qarz · %(code)s") % {"code": res.code},
                detail=f"{res.guest.full_name} · {folio.balance}",
                url_name="folio:detail",
                pk=res.pk,
            )
        )

    if tenant.has_feature("inventory"):
        from inventory.services import (
            expired_stock_items,
            expiring_soon_stock_items,
            low_stock_items,
        )

        for item in expired_stock_items(tenant, hotel=hotel)[:5]:
            items.append(
                notification_entry(
                    kind="stock_expired",
                    title=_("Muddati o‘tgan · %(name)s") % {"name": item.name},
                    detail=_("%(qty)s %(unit)s · %(d)s")
                    % {
                        "qty": item.quantity_on_hand,
                        "unit": item.get_unit_display(),
                        "d": item.expiry_date,
                    },
                    url_name="inventory:list",
                    object_id=item.pk,
                )
            )

        for item in expiring_soon_stock_items(tenant, hotel=hotel)[:5]:
            days = item.days_until_expiry
            items.append(
                notification_entry(
                    kind="stock_expiring",
                    title=_("Muddat yaqin · %(name)s") % {"name": item.name},
                    detail=_("%(days)s kun · %(d)s")
                    % {"days": days if days is not None else "—", "d": item.expiry_date},
                    url_name="inventory:list",
                    object_id=item.pk,
                )
            )

        for item in low_stock_items(tenant, hotel=hotel).order_by("quantity_on_hand")[:4]:
            items.append(
                notification_entry(
                    kind="stock",
                    title=_("Kam ombor · %(name)s") % {"name": item.name},
                    detail=_("%(qty)s %(unit)s (min %(min)s)")
                    % {
                        "qty": item.quantity_on_hand,
                        "unit": item.get_unit_display(),
                        "min": item.reorder_level,
                    },
                    url_name="inventory:list",
                    object_id=item.pk,
                )
            )

    if tenant.has_feature("maintenance"):
        open_tickets = MaintenanceTicket.objects.filter(
            tenant=tenant,
            status__in=[
                MaintenanceTicket.Status.OPEN,
                MaintenanceTicket.Status.IN_PROGRESS,
            ],
        ).select_related("room")
        if hotel is not None:
            open_tickets = open_tickets.filter(room__property=hotel)
        for ticket in open_tickets.order_by("-created_at")[:4]:
            items.append(
                notification_entry(
                    kind="maintenance",
                    title=_("Ta’mir · %(title)s") % {"title": ticket.title},
                    detail=ticket.room.number if ticket.room_id else "—",
                    url_name="maintenance:list",
                    object_id=ticket.pk,
                )
            )

    if dismissed:
        items = [i for i in items if i["key"] not in dismissed]
    items = items[:16]
    return {"items": items, "count": len(items), "day": today}
