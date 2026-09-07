import json
from datetime import date

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from .models import WidgetConfig
from .services import WidgetError, create_web_booking, resolve_widget, room_type_availability
from .services import resolve_property as widget_property


def _apply_cors(request, response, config: WidgetConfig | None):
    origin = request.META.get("HTTP_ORIGIN", "")
    if config and origin and config.origin_allowed(origin):
        response["Access-Control-Allow-Origin"] = origin
        response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type"
        response["Vary"] = "Origin"
    return response


def _json_error(message, code="error", status=400):
    return JsonResponse({"ok": False, "error": message, "code": code}, status=status)


@require_http_methods(["GET", "OPTIONS"])
def api_availability(request, tenant_slug, branch_code=None):
    if request.method == "OPTIONS":
        try:
            config, _tenant = resolve_widget(tenant_slug, branch_code)
        except WidgetError:
            return JsonResponse({})
        return _apply_cors(request, JsonResponse({}), config)

    try:
        config, tenant = resolve_widget(tenant_slug, branch_code)
    except WidgetError as exc:
        return _json_error(exc.message, exc.code, status=403)

    check_in_s = request.GET.get("check_in", "")
    check_out_s = request.GET.get("check_out", "")
    try:
        adults = max(1, int(request.GET.get("adults", "2")))
    except ValueError:
        adults = 2
    try:
        check_in = date.fromisoformat(check_in_s)
        check_out = date.fromisoformat(check_out_s)
    except ValueError:
        return _json_error(_("Sanani to‘g‘ri kiriting."), "dates")

    try:
        prop = widget_property(config, tenant)
        rows = room_type_availability(
            tenant, prop, check_in=check_in, check_out=check_out, adults=adults
        )
    except WidgetError as exc:
        return _json_error(exc.message, exc.code)

    payload = {
        "ok": True,
        "hotel": prop.name,
        "branch": prop.branch_code,
        "currency": tenant.currency,
        "check_in": check_in.isoformat(),
        "check_out": check_out.isoformat(),
        "room_types": rows,
    }
    return _apply_cors(request, JsonResponse(payload), config)


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def api_book(request, tenant_slug, branch_code=None):
    if request.method == "OPTIONS":
        try:
            config, _tenant = resolve_widget(tenant_slug, branch_code)
        except WidgetError:
            return JsonResponse({})
        return _apply_cors(request, JsonResponse({}), config)

    try:
        config, tenant = resolve_widget(tenant_slug, branch_code)
    except WidgetError as exc:
        return _json_error(exc.message, exc.code, status=403)

    if not config.referer_allowed(request.META.get("HTTP_REFERER", "")):
        return _json_error(_("Bu domen ruxsat etilmagan."), "domain", status=403)

    try:
        data = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        return _json_error(_("Noto‘g‘ri JSON."), "json")

    try:
        check_in = date.fromisoformat(data.get("check_in", ""))
        check_out = date.fromisoformat(data.get("check_out", ""))
        room_type_id = int(data.get("room_type_id"))
        adults = max(1, int(data.get("adults", 2)))
        children = max(0, int(data.get("children", 0)))
    except (ValueError, TypeError):
        return _json_error(_("Ma’lumotlar noto‘g‘ri."), "validation")

    try:
        reservation = create_web_booking(
            config,
            tenant,
            room_type_id=room_type_id,
            check_in=check_in,
            check_out=check_out,
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            phone=data.get("phone", ""),
            email=data.get("email", ""),
            adults=adults,
            children=children,
            notes=data.get("notes", ""),
        )
    except WidgetError as exc:
        status = 409 if exc.code == "unavailable" else 400
        return _json_error(exc.message, exc.code, status=status)

    payload = {
        "ok": True,
        "code": reservation.code,
        "status": reservation.status,
        "message": _("Bron qabul qilindi! Kod: %(code)s") % {"code": reservation.code},
    }
    return _apply_cors(request, JsonResponse(payload), config)


@xframe_options_exempt
@require_GET
def widget_frame(request, tenant_slug, branch_code=None):
    try:
        config, tenant = resolve_widget(tenant_slug, branch_code)
    except WidgetError as exc:
        return render(
            request,
            "widget/disabled.html",
            {"message": exc.message},
            status=403,
        )

    referer = request.META.get("HTTP_REFERER", "")
    if referer and not config.referer_allowed(referer):
        return render(
            request,
            "widget/disabled.html",
            {"message": _("Bu saytdan widget ochishga ruxsat yo‘q.")},
            status=403,
        )

    prop = widget_property(config, tenant)
    base = getattr(settings, "WIDGET_BASE_URL", "").rstrip("/") or request.build_absolute_uri("/").rstrip("/")
    branch = prop.branch_code
    return render(
        request,
        "widget/booking.html",
        {
            "tenant": tenant,
            "config": config,
            "property": prop,
            "tenant_slug": tenant_slug,
            "branch_code": branch,
            "api_base": base,
            "welcome_title": config.welcome_title or prop.name,
            "welcome_text": config.welcome_text or _("Onlayn bron — real vaqt bandligi"),
        },
    )


@require_GET
def widget_legacy_redirect(request, tenant_slug):
    try:
        config, tenant = resolve_widget(tenant_slug, None)
    except WidgetError as exc:
        return render(request, "widget/disabled.html", {"message": exc.message}, status=403)
    return redirect("widget:frame", tenant_slug=tenant_slug, branch_code=config.hotel.branch_code)
