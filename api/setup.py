"""Property / rooms / services catalog API — additive; web HTML untouched."""

from datetime import date, time
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from core.roles import PROPERTY_ADMIN
from properties.models import Floor, PropertySettings, RatePlan, Room, RoomType, SeasonRate
from services.models import ServiceItem
from tenants.models import TenantMembership

from .auth import api_login_required, api_role_required, json_error, json_ok, parse_json


def _err(exc):
    if hasattr(exc, "messages"):
        return json_error("; ".join(str(m) for m in exc.messages))
    return json_error(str(exc))


def _dec(v, field="amount"):
    try:
        return Decimal(str(v).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(f"Valid {field} required.") from exc


def _rate_row(rp: RatePlan) -> dict:
    return {
        "id": rp.pk,
        "name": rp.name,
        "code": rp.code,
        "room_type_id": rp.room_type_id,
        "room_type": rp.room_type.name if rp.room_type_id else None,
        "price": str(rp.price),
        "extra_adult_price": str(rp.extra_adult_price),
        "currency": rp.currency,
        "is_default": rp.is_default,
        "is_active": rp.is_active,
        "seasons": [
            {
                "id": s.pk,
                "name": s.name,
                "date_from": s.date_from.isoformat(),
                "date_to": s.date_to.isoformat(),
                "price": str(s.price),
            }
            for s in rp.seasons.all().order_by("date_from")
        ],
    }


def _settings_row(s: PropertySettings) -> dict:
    return {
        "tax_percent": str(s.tax_percent),
        "early_checkin_fee": str(s.early_checkin_fee),
        "late_checkout_fee": str(s.late_checkout_fee),
        "emehmon_fee": str(s.emehmon_fee),
        "cancel_fee_percent": str(s.cancel_fee_percent),
        "no_show_fee_percent": str(s.no_show_fee_percent),
        "checkin_time": s.checkin_time.strftime("%H:%M") if s.checkin_time else None,
        "checkout_time": s.checkout_time.strftime("%H:%M") if s.checkout_time else None,
        "require_id_on_checkin": s.require_id_on_checkin,
    }


@api_login_required
@api_role_required(*PROPERTY_ADMIN, TenantMembership.Role.MANAGER)
@require_GET
def property_settings(request):
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    s, _ = PropertySettings.objects.get_or_create(
        tenant=request.tenant, property=hotel
    )
    return json_ok(_settings_row(s))


@api_login_required
@api_role_required(*PROPERTY_ADMIN, TenantMembership.Role.MANAGER)
@require_POST
def property_settings_update(request):
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    s, _ = PropertySettings.objects.get_or_create(
        tenant=request.tenant, property=hotel
    )
    data = parse_json(request)
    money_fields = (
        "tax_percent",
        "early_checkin_fee",
        "late_checkout_fee",
        "emehmon_fee",
        "cancel_fee_percent",
        "no_show_fee_percent",
    )
    try:
        for f in money_fields:
            if f in data and data[f] not in (None, ""):
                setattr(s, f, _dec(data[f], f))
        for tf, attr in (("checkin_time", "checkin_time"), ("checkout_time", "checkout_time")):
            if tf in data and data[tf]:
                hh, mm = str(data[tf]).strip().split(":")[:2]
                setattr(s, attr, time(int(hh), int(mm)))
        if "require_id_on_checkin" in data:
            s.require_id_on_checkin = bool(data["require_id_on_checkin"])
        s.save()
        return json_ok(_settings_row(s))
    except (ValidationError, ValueError, TypeError) as exc:
        return _err(exc) if isinstance(exc, ValidationError) else json_error(str(exc))


@api_login_required
@api_role_required(*PROPERTY_ADMIN, TenantMembership.Role.MANAGER)
@require_GET
def room_types(request):
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    items = [
        {
            "id": rt.pk,
            "name": rt.name,
            "code": rt.code,
            "base_price": str(rt.base_price),
            "capacity_adults": rt.capacity_adults,
            "is_active": rt.is_active,
        }
        for rt in RoomType.objects.filter(
            tenant=request.tenant, property=hotel
        ).order_by("name")
    ]
    return json_ok({"items": items})


@api_login_required
@api_role_required(*PROPERTY_ADMIN, TenantMembership.Role.MANAGER)
@require_POST
def room_type_create(request):
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    data = parse_json(request)
    name = (data.get("name") or "").strip()
    code = (data.get("code") or "").strip().lower()
    if not name or not code:
        return json_error("name and code required.")
    try:
        price = _dec(data.get("base_price") or "0", "base_price")
    except ValidationError as exc:
        return _err(exc)
    rt = RoomType.objects.create(
        tenant=request.tenant,
        property=hotel,
        name=name,
        code=code,
        base_price=price,
        capacity_adults=int(data.get("capacity_adults") or 2),
        is_active=True,
    )
    return json_ok(
        {
            "id": rt.pk,
            "name": rt.name,
            "code": rt.code,
            "base_price": str(rt.base_price),
        },
        status=201,
    )


@api_login_required
@api_role_required(*PROPERTY_ADMIN, TenantMembership.Role.MANAGER)
@require_GET
def rooms_admin(request):
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    items = [
        {
            "id": r.pk,
            "number": r.number,
            "status": r.status,
            "is_active": r.is_active,
            "room_type_id": r.room_type_id,
            "room_type": r.room_type.name if r.room_type_id else "",
            "floor_id": r.floor_id,
            "floor": r.floor.number if r.floor_id else None,
        }
        for r in Room.objects.filter(tenant=request.tenant, property=hotel)
        .select_related("room_type", "floor")
        .order_by("number")
    ]
    floors = [
        {"id": f.pk, "number": f.number, "name": f.name or ""}
        for f in Floor.objects.filter(tenant=request.tenant, property=hotel).order_by(
            "number"
        )
    ]
    return json_ok({"items": items, "floors": floors})


@api_login_required
@api_role_required(*PROPERTY_ADMIN, TenantMembership.Role.MANAGER)
@require_POST
def room_create(request):
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    data = parse_json(request)
    number = (data.get("number") or "").strip()
    if not number:
        return json_error("number required.")
    rt = RoomType.objects.filter(
        pk=data.get("room_type_id"), tenant=request.tenant, property=hotel
    ).first()
    if rt is None:
        return json_error("room_type_id required / not found.")
    floor = None
    if data.get("floor_id"):
        floor = Floor.objects.filter(
            pk=data["floor_id"], tenant=request.tenant, property=hotel
        ).first()
    if Room.objects.filter(
        tenant=request.tenant, property=hotel, number=number
    ).exists():
        return json_error("Room number already exists.")
    room = Room.objects.create(
        tenant=request.tenant,
        property=hotel,
        room_type=rt,
        floor=floor,
        number=number,
        is_active=True,
    )
    return json_ok(
        {
            "id": room.pk,
            "number": room.number,
            "room_type_id": room.room_type_id,
            "status": room.status,
        },
        status=201,
    )


@api_login_required
@api_role_required(*PROPERTY_ADMIN, TenantMembership.Role.MANAGER, TenantMembership.Role.RECEPTIONIST)
@require_http_methods(["GET", "POST"])
def services_catalog(request):
    if request.method == "GET":
        qs = ServiceItem.objects.filter(tenant=request.tenant)
        if (request.GET.get("active") or "1") == "1":
            qs = qs.filter(is_active=True)
        items = [
            {
                "id": s.pk,
                "name": s.name,
                "code": s.code,
                "unit_price": str(s.unit_price),
                "currency": s.currency,
                "is_active": s.is_active,
            }
            for s in qs.order_by("name")[:200]
        ]
        return json_ok({"items": items})

    data = parse_json(request)
    name = (data.get("name") or "").strip()
    code = (data.get("code") or "").strip().lower()
    if not name or not code:
        return json_error("name and code required.")
    try:
        price = _dec(data.get("unit_price") or "0", "unit_price")
    except ValidationError as exc:
        return _err(exc)
    if ServiceItem.objects.filter(tenant=request.tenant, code=code).exists():
        return json_error("Service code already exists.")
    item = ServiceItem.objects.create(
        tenant=request.tenant,
        name=name,
        code=code,
        unit_price=price,
        currency=(data.get("currency") or request.tenant.currency or "UZS").upper(),
        description=(data.get("description") or "").strip(),
        is_active=True,
    )
    return json_ok(
        {
            "id": item.pk,
            "name": item.name,
            "code": item.code,
            "unit_price": str(item.unit_price),
        },
        status=201,
    )


@api_login_required
@api_role_required(*PROPERTY_ADMIN, TenantMembership.Role.MANAGER)
@require_POST
def service_update(request, pk):
    item = ServiceItem.objects.filter(pk=pk, tenant=request.tenant).first()
    if item is None:
        return json_error("Service not found.", status=404)
    data = parse_json(request)
    if "name" in data:
        item.name = (data.get("name") or "").strip() or item.name
    if "unit_price" in data and data["unit_price"] not in (None, ""):
        try:
            item.unit_price = _dec(data["unit_price"], "unit_price")
        except ValidationError as exc:
            return _err(exc)
    if "is_active" in data:
        item.is_active = bool(data["is_active"])
    if "description" in data:
        item.description = (data.get("description") or "").strip()
    item.save()
    return json_ok(
        {
            "id": item.pk,
            "name": item.name,
            "code": item.code,
            "unit_price": str(item.unit_price),
            "is_active": item.is_active,
        }
    )


@api_login_required
@api_role_required(*PROPERTY_ADMIN, TenantMembership.Role.MANAGER)
@require_GET
def rate_plans(request):
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    qs = (
        RatePlan.objects.filter(tenant=request.tenant, property=hotel)
        .select_related("room_type")
        .prefetch_related("seasons")
        .order_by("name")
    )
    return json_ok({"items": [_rate_row(rp) for rp in qs]})


@api_login_required
@api_role_required(*PROPERTY_ADMIN, TenantMembership.Role.MANAGER)
@require_POST
def rate_plan_create(request):
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    data = parse_json(request)
    name = (data.get("name") or "").strip()
    code = (data.get("code") or "").strip().lower()
    if not name or not code:
        return json_error("name and code required.")
    try:
        rt_id = int(data.get("room_type_id"))
        price = _dec(data.get("price") or "0", "price")
        extra = _dec(data.get("extra_adult_price") or "0", "extra_adult_price")
    except (TypeError, ValueError, ValidationError) as exc:
        return _err(exc) if isinstance(exc, ValidationError) else json_error(str(exc))
    rt = RoomType.objects.filter(
        pk=rt_id, tenant=request.tenant, property=hotel
    ).first()
    if rt is None:
        return json_error("Room type not found.", status=404)
    if RatePlan.objects.filter(property=hotel, code=code).exists():
        return json_error("Rate plan code already exists.")
    rp = RatePlan.objects.create(
        tenant=request.tenant,
        property=hotel,
        name=name,
        code=code,
        room_type=rt,
        price=price,
        extra_adult_price=extra,
        currency=(data.get("currency") or request.tenant.currency or "UZS").upper(),
        is_default=bool(data.get("is_default")),
        is_active=True,
    )
    if rp.is_default:
        RatePlan.objects.filter(
            property=hotel, room_type=rt, is_default=True
        ).exclude(pk=rp.pk).update(is_default=False)
    return json_ok(_rate_row(rp), status=201)


@api_login_required
@api_role_required(*PROPERTY_ADMIN, TenantMembership.Role.MANAGER)
@require_POST
def rate_plan_update(request, pk):
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    rp = (
        RatePlan.objects.filter(pk=pk, tenant=request.tenant, property=hotel)
        .select_related("room_type")
        .prefetch_related("seasons")
        .first()
    )
    if rp is None:
        return json_error("Rate plan not found.", status=404)
    data = parse_json(request)
    try:
        if "name" in data:
            rp.name = (data.get("name") or "").strip() or rp.name
        if "price" in data and data["price"] not in (None, ""):
            rp.price = _dec(data["price"], "price")
        if "extra_adult_price" in data and data["extra_adult_price"] not in (None, ""):
            rp.extra_adult_price = _dec(data["extra_adult_price"], "extra_adult_price")
        if "is_default" in data:
            rp.is_default = bool(data["is_default"])
        if "is_active" in data:
            rp.is_active = bool(data["is_active"])
        rp.save()
        if rp.is_default:
            RatePlan.objects.filter(
                property=hotel, room_type_id=rp.room_type_id, is_default=True
            ).exclude(pk=rp.pk).update(is_default=False)
        return json_ok(_rate_row(rp))
    except ValidationError as exc:
        return _err(exc)


@api_login_required
@api_role_required(*PROPERTY_ADMIN, TenantMembership.Role.MANAGER)
@require_POST
def rate_plan_season_create(request, pk):
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    rp = RatePlan.objects.filter(
        pk=pk, tenant=request.tenant, property=hotel
    ).first()
    if rp is None:
        return json_error("Rate plan not found.", status=404)
    data = parse_json(request)
    name = (data.get("name") or "").strip() or "Season"
    try:
        d_from = date.fromisoformat(str(data.get("date_from") or "").strip())
        d_to = date.fromisoformat(str(data.get("date_to") or "").strip())
        price = _dec(data.get("price") or "0", "price")
    except (TypeError, ValueError, ValidationError) as exc:
        return _err(exc) if isinstance(exc, ValidationError) else json_error(
            "Invalid date_from/date_to/price."
        )
    if d_from > d_to:
        return json_error("date_from must be on or before date_to.")
    season = SeasonRate.objects.create(
        tenant=request.tenant,
        rate_plan=rp,
        name=name,
        date_from=d_from,
        date_to=d_to,
        price=price,
    )
    return json_ok(
        {
            "id": season.pk,
            "name": season.name,
            "date_from": season.date_from.isoformat(),
            "date_to": season.date_to.isoformat(),
            "price": str(season.price),
        },
        status=201,
    )


@api_login_required
@api_role_required(*PROPERTY_ADMIN, TenantMembership.Role.MANAGER)
@require_http_methods(["GET", "POST"])
def floors_admin(request):
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    if request.method == "GET":
        items = [
            {"id": f.pk, "number": f.number, "name": f.name or ""}
            for f in Floor.objects.filter(
                tenant=request.tenant, property=hotel
            ).order_by("number")
        ]
        return json_ok({"items": items})
    data = parse_json(request)
    try:
        number = int(data.get("number"))
    except (TypeError, ValueError):
        return json_error("number required (integer).")
    name = (data.get("name") or "").strip()
    if Floor.objects.filter(
        tenant=request.tenant, property=hotel, number=number
    ).exists():
        return json_error("Floor number already exists.")
    floor = Floor.objects.create(
        tenant=request.tenant, property=hotel, number=number, name=name
    )
    return json_ok(
        {"id": floor.pk, "number": floor.number, "name": floor.name or ""},
        status=201,
    )


@api_login_required
@api_role_required(*PROPERTY_ADMIN, TenantMembership.Role.MANAGER)
@require_POST
def floor_update(request, pk):
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    floor = Floor.objects.filter(
        pk=pk, tenant=request.tenant, property=hotel
    ).first()
    if floor is None:
        return json_error("Floor not found.", status=404)
    data = parse_json(request)
    if "name" in data:
        floor.name = (data.get("name") or "").strip()
    if "number" in data and data["number"] not in (None, ""):
        try:
            num = int(data["number"])
        except (TypeError, ValueError):
            return json_error("Invalid number.")
        clash = (
            Floor.objects.filter(tenant=request.tenant, property=hotel, number=num)
            .exclude(pk=floor.pk)
            .exists()
        )
        if clash:
            return json_error("Floor number already exists.")
        floor.number = num
    floor.save()
    return json_ok({"id": floor.pk, "number": floor.number, "name": floor.name or ""})


@api_login_required
@api_role_required(*PROPERTY_ADMIN, TenantMembership.Role.MANAGER)
@require_POST
def room_type_update(request, pk):
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    rt = RoomType.objects.filter(
        pk=pk, tenant=request.tenant, property=hotel
    ).first()
    if rt is None:
        return json_error("Room type not found.", status=404)
    data = parse_json(request)
    if "name" in data:
        rt.name = (data.get("name") or "").strip() or rt.name
    if "base_price" in data and data["base_price"] not in (None, ""):
        try:
            rt.base_price = _dec(data["base_price"], "base_price")
        except ValidationError as exc:
            return _err(exc)
    if "capacity_adults" in data and data["capacity_adults"] not in (None, ""):
        try:
            rt.capacity_adults = int(data["capacity_adults"])
        except (TypeError, ValueError):
            return json_error("Invalid capacity_adults.")
    if "is_active" in data:
        rt.is_active = bool(data["is_active"])
    rt.save()
    return json_ok(
        {
            "id": rt.pk,
            "name": rt.name,
            "code": rt.code,
            "base_price": str(rt.base_price),
            "capacity_adults": rt.capacity_adults,
            "is_active": rt.is_active,
        }
    )


@api_login_required
@api_role_required(*PROPERTY_ADMIN, TenantMembership.Role.MANAGER)
@require_POST
def room_update(request, pk):
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    room = Room.objects.filter(
        pk=pk, tenant=request.tenant, property=hotel
    ).first()
    if room is None:
        return json_error("Room not found.", status=404)
    data = parse_json(request)
    if "number" in data:
        number = (data.get("number") or "").strip()
        if not number:
            return json_error("number required.")
        clash = (
            Room.objects.filter(tenant=request.tenant, property=hotel, number=number)
            .exclude(pk=room.pk)
            .exists()
        )
        if clash:
            return json_error("Room number already exists.")
        room.number = number
    if "room_type_id" in data and data["room_type_id"] not in (None, ""):
        rt = RoomType.objects.filter(
            pk=data["room_type_id"], tenant=request.tenant, property=hotel
        ).first()
        if rt is None:
            return json_error("room_type_id not found.")
        room.room_type = rt
    if "floor_id" in data:
        if data["floor_id"] in (None, "", 0, "0"):
            room.floor = None
        else:
            floor = Floor.objects.filter(
                pk=data["floor_id"], tenant=request.tenant, property=hotel
            ).first()
            if floor is None:
                return json_error("floor_id not found.")
            room.floor = floor
    if "is_active" in data:
        room.is_active = bool(data["is_active"])
    room.save()
    return json_ok(
        {
            "id": room.pk,
            "number": room.number,
            "status": room.status,
            "is_active": room.is_active,
            "room_type_id": room.room_type_id,
            "floor_id": room.floor_id,
        }
    )
