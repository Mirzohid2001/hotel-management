import json
from functools import wraps

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from core.roles import nav_permissions
from tenants.models import TenantMembership

from .models import ApiToken


def json_error(message, status=400, **extra):
    body = {"ok": False, "error": message}
    body.update(extra)
    return JsonResponse(body, status=status)


def json_ok(data=None, status=200, **extra):
    body = {"ok": True}
    if data is not None:
        body["data"] = data
    body.update(extra)
    return JsonResponse(body, status=status)


def parse_json(request) -> dict:
    if not request.body:
        return {}
    try:
        raw = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _bearer_token(request) -> str | None:
    auth = request.META.get("HTTP_AUTHORIZATION") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return None


def api_login_required(view):
    """Require Authorization: Bearer <token>. CSRF exempt (token auth)."""

    @csrf_exempt
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        key = _bearer_token(request)
        if not key:
            return json_error("Authentication required.", status=401)
        token = (
            ApiToken.objects.select_related("user", "tenant")
            .filter(key=key, revoked_at__isnull=True)
            .first()
        )
        if token is None or not token.user.is_active:
            return json_error("Invalid or revoked token.", status=401)

        tenant_id = request.META.get("HTTP_X_TENANT_ID") or request.GET.get("tenant_id")
        membership_qs = TenantMembership.objects.filter(
            user=token.user, is_active=True, tenant__is_active=True
        ).select_related("tenant")
        if tenant_id:
            membership = membership_qs.filter(tenant_id=tenant_id).first()
        else:
            membership = membership_qs.filter(tenant_id=token.tenant_id).first()
            if membership is None:
                membership = membership_qs.order_by("tenant__name").first()
        if membership is None:
            return json_error("No active hotel membership.", status=403)

        token.touch()
        request.user = token.user
        request.api_token = token
        request.membership = membership
        request.tenant = membership.tenant
        request.active_property = None
        from properties.active import resolve_active_property

        # Optional hotel scope via header (same idea as web active property)
        hotel_id = request.META.get("HTTP_X_HOTEL_ID") or request.GET.get("hotel_id")
        if hotel_id:
            from properties.models import Property

            hotel = Property.objects.filter(
                pk=hotel_id, tenant=request.tenant, is_active=True
            ).first()
            if hotel is None:
                return json_error("Hotel not found.", status=404)
            request.active_property = hotel
        else:
            request.active_property = resolve_active_property(request)

        return view(request, *args, **kwargs)

    return wrapper


def api_role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            membership = getattr(request, "membership", None)
            if membership is None or membership.role not in roles:
                return json_error("Permission denied.", status=403)
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def me_payload(request) -> dict:
    membership = request.membership
    tenant = request.tenant
    hotel = getattr(request, "active_property", None)
    from properties.active import tenant_properties

    hotels = [
        {
            "id": p.pk,
            "name": p.name,
            "branch_code": getattr(p, "branch_code", "") or "",
        }
        for p in tenant_properties(tenant, membership)
    ]
    return {
        "user": {
            "id": request.user.pk,
            "username": request.user.get_username(),
            "full_name": request.user.get_full_name() or request.user.get_username(),
        },
        "tenant": {
            "id": tenant.pk,
            "name": tenant.name,
            "slug": tenant.slug,
            "currency": tenant.currency,
        },
        "role": membership.role,
        "permissions": nav_permissions(membership.role),
        "hotel": (
            {
                "id": hotel.pk,
                "name": hotel.name,
                "branch_code": getattr(hotel, "branch_code", "") or "",
            }
            if hotel
            else None
        ),
        "hotels": hotels,
    }
