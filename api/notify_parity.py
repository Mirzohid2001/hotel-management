"""Notifications + print URL wiring helpers live in urls; this module is notify API."""

from django.core.cache import cache
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.notifications import build_notifications
from core.roles import FLOOR_VIEW

from .auth import api_login_required, api_role_required, json_error, json_ok, parse_json


def _dismiss_cache_key(request) -> str:
    day = timezone.localdate()
    return f"api_notify_dismiss:{request.user.pk}:{request.tenant.pk}:{day.isoformat()}"


def _dismissed_for(request) -> set[str]:
    return set(cache.get(_dismiss_cache_key(request)) or [])


@api_login_required
@api_role_required(*FLOOR_VIEW)
@require_GET
def notifications_list(request):
    hotel = getattr(request, "active_property", None)
    dismissed = _dismissed_for(request)
    payload = build_notifications(request.tenant, hotel=hotel, dismissed=dismissed)
    items = []
    for n in payload.get("items") or []:
        url_name = n.get("url_name") or ""
        raw_id = n.get("pk") if n.get("pk") is not None else n.get("object_id")
        target = ""
        if url_name in {"bookings:detail", "folio:detail"}:
            target = "reservation"
        elif url_name == "maintenance:list":
            target = "maintenance"
        elif url_name == "inventory:list":
            target = "inventory"
        items.append(
            {
                "key": n["key"],
                "kind": n["kind"],
                "title": n["title"],
                "detail": n["detail"],
                "pk": raw_id,
                "url_name": url_name,
                "target": target,
                "target_id": raw_id,
            }
        )
    return json_ok(
        {
            "day": payload.get("day"),
            "count": len(items),
            "items": items,
        }
    )


@api_login_required
@api_role_required(*FLOOR_VIEW)
@require_POST
def notifications_dismiss(request):
    data = parse_json(request)
    key = (data.get("key") or "").strip()
    if not key:
        return json_error("key required.")
    cache_key = _dismiss_cache_key(request)
    current = list(cache.get(cache_key) or [])
    if key not in current:
        current.append(key)
    cache.set(cache_key, current, timeout=60 * 60 * 36)
    return json_ok({"dismissed": key, "count": len(current)})
