from django.utils.translation import gettext as _
from django.contrib import messages
from django.db.models import ProtectedError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods, require_POST

from core.htmx import oob_select_response
from core.mixins import feature_required, role_required, tenant_login_required
from core.roles import PROPERTY_ADMIN

from .active import set_active_property, set_all_properties
from .forms import (
    FloorForm,
    FloorQuickForm,
    PropertyForm,
    PropertySettingsForm,
    RatePlanForm,
    RoomForm,
    RoomTypeForm,
    RoomTypeQuickForm,
    SeasonRateForm,
)
from .models import Floor, Property, PropertySettings, RatePlan, Room, RoomType, SeasonRate
from .services import (
    build_rate_matrix,
    missing_room_type_presets,
    prune_to_standard_room_types,
    seed_standard_room_types,
    suggest_base_price,
)
from .room_type_presets import STANDARD_ROOM_TYPE_CODES, STANDARD_ROOM_TYPE_PRESETS
from decimal import Decimal, InvalidOperation


def _unique_room_type_code(prop: Property, base: str) -> str:
    base = (slugify(base) or "type")[:36]
    code = base
    n = 2
    while RoomType.objects.filter(property=prop, code=code).exists():
        suffix = f"-{n}"
        code = f"{base[: 40 - len(suffix)]}{suffix}"
        n += 1
    return code


def _get_property(request, pk):
    prop = get_object_or_404(Property, pk=pk, tenant=request.tenant)
    from tenants.property_access import can_access_property

    if not can_access_property(request.membership, prop):
        raise Http404
    return prop


@tenant_login_required
@require_POST
def switch_property(request, pk):
    prop = get_object_or_404(Property, pk=pk, tenant=request.tenant, is_active=True)
    if not set_active_property(request, prop):
        messages.error(request, _("Bu filialga ruxsat yo‘q."))
        return redirect(request.POST.get("next") or "/")
    messages.info(request, _("Faol filial: %(n)s") % {"n": prop.display_label})
    next_url = request.POST.get("next") or request.GET.get("next") or "/"
    if not str(next_url).startswith("/"):
        next_url = "/"
    return redirect(next_url)


@tenant_login_required
@require_POST
def switch_all_properties(request):
    if not set_all_properties(request):
        messages.error(request, _("Barcha filiallar rejimi mavjud emas."))
    else:
        messages.info(request, _("Barcha filiallar (yig‘ma ko‘rinish)"))
    next_url = request.POST.get("next") or "/"
    if not str(next_url).startswith("/"):
        next_url = "/"
    return redirect(next_url)


@role_required(*PROPERTY_ADMIN)
def property_list(request):
    from properties.active import tenant_properties

    props = tenant_properties(request.tenant, request.membership)
    return render(request, "properties/property_list.html", {"properties": props})


@role_required(*PROPERTY_ADMIN)
@require_http_methods(["GET", "POST"])
def property_create(request):
    form = PropertyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        active_count = Property.objects.filter(tenant=request.tenant, is_active=True).count()
        if not request.tenant.check_limit("properties", active_count):
            messages.error(request, _("Tarif bo‘yicha filiallar limiti tugagan."))
            return redirect("properties:list")
        prop = form.save(commit=False)
        prop.tenant = request.tenant
        prop.save()
        PropertySettings.objects.create(tenant=request.tenant, property=prop)
        messages.success(request, _("Mehmonxona yaratildi."))
        return redirect("properties:detail", pk=prop.pk)
    return render(request, "properties/property_form.html", {"form": form, "title": _("Yangi mehmonxona")})


@role_required(*PROPERTY_ADMIN)
def property_detail(request, pk):
    prop = _get_property(request, pk)
    settings_obj, _created = PropertySettings.objects.get_or_create(tenant=request.tenant, property=prop)
    missing_presets = missing_room_type_presets(prop)
    extras = (
        prop.room_types.filter(is_active=True)
        .exclude(code__in=STANDARD_ROOM_TYPE_CODES)
        .values_list("code", flat=True)
    )
    return render(
        request,
        "properties/property_detail.html",
        {
            "property_obj": prop,
            "settings_obj": settings_obj,
            "room_types": prop.room_types.filter(is_active=True),
            "rooms": prop.rooms.select_related("room_type", "floor"),
            "rate_plans": prop.rate_plans.select_related("room_type").prefetch_related("seasons"),
            "floors": prop.floors.all(),
            "missing_room_presets": missing_presets,
            "extra_room_type_codes": list(extras),
            "suggested_base_price": suggest_base_price(prop),
            "all_room_presets": STANDARD_ROOM_TYPE_PRESETS,
        },
    )


@role_required(*PROPERTY_ADMIN)
@require_POST
def room_types_seed(request, property_id):
    """Standart xona turlari (Double/Twin/Triple) — yetishmayotganlar + ortiqchalarni yig‘ish."""
    prop = _get_property(request, property_id)
    raw = (request.POST.get("base_price") or "").strip()
    base_price = None
    if raw:
        try:
            base_price = Decimal(raw.replace(" ", "").replace(",", ""))
        except (InvalidOperation, ValueError):
            messages.error(request, _("Asosiy narx noto‘g‘ri."))
            return redirect("properties:detail", pk=prop.pk)
        if base_price < 0:
            messages.error(request, _("Asosiy narx manfiy bo‘lishi mumkin emas."))
            return redirect("properties:detail", pk=prop.pk)

    with_rates = request.POST.get("with_rates") == "1"
    result = seed_standard_room_types(
        tenant=request.tenant,
        prop=prop,
        base_price=base_price,
        with_rate_plans=with_rates,
    )
    pruned = prune_to_standard_room_types(prop=prop)
    n = len(result["created_types"])
    if n:
        messages.success(
            request,
            _("%(n)s ta xona turi qo‘shildi (baza: %(p)s).")
            % {"n": n, "p": result["base_price"]},
        )
    if pruned["deactivated"] or pruned["remapped_rooms"]:
        messages.success(
            request,
            _(
                "Faqat Double/Twin/Triple qoldi: %(rooms)s xona qayta biriktirildi, "
                "%(off)s tur o‘chirildi."
            )
            % {
                "rooms": pruned["remapped_rooms"],
                "off": ", ".join(pruned["deactivated"]) or "—",
            },
        )
    elif not n:
        messages.info(request, _("Barcha standart turlar allaqachon mavjud."))
    return redirect("properties:detail", pk=prop.pk)


@role_required(*PROPERTY_ADMIN)
@require_http_methods(["GET", "POST"])
def property_settings_edit(request, pk):
    prop = _get_property(request, pk)
    settings_obj, _created = PropertySettings.objects.get_or_create(tenant=request.tenant, property=prop)
    form = PropertySettingsForm(request.POST or None, instance=settings_obj)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.tenant = request.tenant
        obj.property = prop
        obj.save()
        messages.success(request, _("Sozlamalar saqlandi."))
        return redirect("properties:detail", pk=prop.pk)
    return render(
        request,
        "properties/settings_form.html",
        {"form": form, "property_obj": prop},
    )


@role_required(*PROPERTY_ADMIN)
@require_http_methods(["GET", "POST"])
def room_type_create(request, property_id):
    prop = _get_property(request, property_id)
    form = RoomTypeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.tenant = request.tenant
        obj.property = prop
        obj.save()
        messages.success(request, _("Xona turi qo‘shildi."))
        return redirect("properties:detail", pk=prop.pk)
    return render(
        request,
        "properties/simple_form.html",
        {
            "form": form,
            "title": _("Xona turi"),
            "property_obj": prop,
            "room_presets": STANDARD_ROOM_TYPE_PRESETS,
            "suggested_base_price": suggest_base_price(prop),
        },
    )


@role_required(*PROPERTY_ADMIN)
@require_http_methods(["GET", "POST"])
def room_create(request, property_id):
    prop = _get_property(request, property_id)
    if not request.tenant.check_limit("rooms", Room.objects.filter(tenant=request.tenant, is_active=True).count()):
        messages.error(request, _("Tarif bo‘yicha xonalar limiti tugagan."))
        return redirect("properties:detail", pk=prop.pk)
    form = RoomForm(request.POST or None, property_obj=prop)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.tenant = request.tenant
        obj.property = prop
        obj.save()
        messages.success(request, _("Xona qo‘shildi."))
        return redirect("properties:detail", pk=prop.pk)
    return render(
        request,
        "properties/room_form.html",
        {"form": form, "title": _("Yangi xona"), "property_obj": prop},
    )


@role_required(*PROPERTY_ADMIN)
@require_http_methods(["GET", "POST"])
def room_edit(request, property_id, pk):
    prop = _get_property(request, property_id)
    room = get_object_or_404(Room, pk=pk, property=prop, tenant=request.tenant)
    form = RoomForm(request.POST or None, instance=room, property_obj=prop)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Xona yangilandi."))
        return redirect("properties:detail", pk=prop.pk)
    return render(
        request,
        "properties/room_form.html",
        {
            "form": form,
            "title": _("Xonani tahrirlash"),
            "property_obj": prop,
            "room": room,
            "delete_url": reverse("properties:room_delete", args=[prop.pk, room.pk]),
            "delete_confirm": _("Bu xonani o‘chirishni xohlaysizmi?"),
        },
    )


@role_required(*PROPERTY_ADMIN)
@require_POST
def room_delete(request, property_id, pk):
    prop = _get_property(request, property_id)
    room = get_object_or_404(Room, pk=pk, property=prop, tenant=request.tenant)
    room.delete()
    messages.success(request, _("Xona o‘chirildi."))
    return redirect("properties:detail", pk=prop.pk)


@role_required(*PROPERTY_ADMIN)
@require_http_methods(["GET", "POST"])
def room_type_edit(request, property_id, pk):
    prop = _get_property(request, property_id)
    room_type = get_object_or_404(RoomType, pk=pk, property=prop, tenant=request.tenant)
    form = RoomTypeForm(request.POST or None, instance=room_type)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Xona turi yangilandi."))
        return redirect("properties:detail", pk=prop.pk)
    return render(
        request,
        "properties/simple_form.html",
        {
            "form": form,
            "title": _("Xona turini tahrirlash"),
            "property_obj": prop,
            "delete_url": reverse("properties:room_type_delete", args=[prop.pk, room_type.pk]),
            "delete_confirm": _(
                "Bu xona turini o‘chirishni xohlaysizmi? Bog‘langan tariflar ham o‘chadi."
            ),
        },
    )


@role_required(*PROPERTY_ADMIN)
@require_POST
def room_type_delete(request, property_id, pk):
    prop = _get_property(request, property_id)
    room_type = get_object_or_404(RoomType, pk=pk, property=prop, tenant=request.tenant)
    room_count = room_type.rooms.count()
    if room_count:
        messages.error(
            request,
            _(
                "Avval shu turga biriktirilgan %(n)s ta xonani boshqa turga o‘tkazing yoki o‘chiring."
            )
            % {"n": room_count},
        )
        return redirect("properties:detail", pk=prop.pk)
    try:
        room_type.delete()
    except ProtectedError:
        messages.error(
            request,
            _("Bu tur bronlarda ishlatilgan — o‘chirib bo‘lmaydi."),
        )
        return redirect("properties:detail", pk=prop.pk)
    messages.success(request, _("Xona turi o‘chirildi."))
    return redirect("properties:detail", pk=prop.pk)


@role_required(*PROPERTY_ADMIN)
@require_http_methods(["GET", "POST"])
def room_type_quick(request, property_id):
    """HTMX: xona turini tez qo‘shish va selectni yangilash."""
    prop = _get_property(request, property_id)
    select_id = request.GET.get("select_id") or request.POST.get("select_id") or "id_room_type"
    field_name = request.GET.get("field_name") or request.POST.get("field_name") or "room_type"
    form = RoomTypeQuickForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        code = (form.cleaned_data.get("code") or "").strip() or _unique_room_type_code(
            prop, form.cleaned_data["name"]
        )
        if RoomType.objects.filter(property=prop, code=code).exists():
            form.add_error("code", _("Bu kod allaqachon mavjud."))
        else:
            obj = RoomType.objects.create(
                tenant=request.tenant,
                property=prop,
                name=form.cleaned_data["name"].strip(),
                code=code,
                base_price=form.cleaned_data["base_price"],
                capacity_adults=form.cleaned_data["capacity_adults"],
            )
            qs = RoomType.objects.filter(property=prop).order_by("name")
            return oob_select_response(
                select_id, field_name, qs, obj.pk, required=True
            )
    return render(
        request,
        "properties/partials/quick_room_type_form.html",
        {
            "form": form,
            "property_obj": prop,
            "select_id": select_id,
            "field_name": field_name,
            "title": _("Yangi xona turi"),
        },
    )


@role_required(*PROPERTY_ADMIN)
@require_http_methods(["GET", "POST"])
def floor_quick(request, property_id):
    """HTMX: qavatni tez qo‘shish va selectni yangilash."""
    prop = _get_property(request, property_id)
    select_id = request.GET.get("select_id") or request.POST.get("select_id") or "id_floor"
    field_name = request.GET.get("field_name") or request.POST.get("field_name") or "floor"
    form = FloorQuickForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        number = form.cleaned_data["number"]
        if Floor.objects.filter(property=prop, number=number).exists():
            form.add_error("number", _("Bu qavat allaqachon mavjud."))
        else:
            obj = Floor.objects.create(
                tenant=request.tenant,
                property=prop,
                number=number,
                name=(form.cleaned_data.get("name") or "").strip(),
            )
            qs = Floor.objects.filter(property=prop).order_by("number")
            return oob_select_response(select_id, field_name, qs, obj.pk)
    return render(
        request,
        "properties/partials/quick_floor_form.html",
        {
            "form": form,
            "property_obj": prop,
            "select_id": select_id,
            "field_name": field_name,
            "title": _("Yangi qavat"),
        },
    )


@role_required(*PROPERTY_ADMIN)
@require_http_methods(["GET", "POST"])
def rate_plan_create(request, property_id):
    prop = _get_property(request, property_id)
    form = RatePlanForm(request.POST or None, property_obj=prop)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.tenant = request.tenant
        obj.property = prop
        obj.save()
        messages.success(request, _("Tarif qo‘shildi."))
        return redirect("properties:detail", pk=prop.pk)
    return render(
        request,
        "properties/simple_form.html",
        {"form": form, "title": _("Tarif rejasi"), "property_obj": prop},
    )


@role_required(*PROPERTY_ADMIN)
@require_http_methods(["GET", "POST"])
def floor_create(request, property_id):
    prop = _get_property(request, property_id)
    form = FloorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.tenant = request.tenant
        obj.property = prop
        obj.save()
        messages.success(request, _("Qavat qo‘shildi."))
        return redirect("properties:detail", pk=prop.pk)
    return render(
        request,
        "properties/simple_form.html",
        {"form": form, "title": _("Qavat"), "property_obj": prop},
    )


@role_required(*PROPERTY_ADMIN)
@require_http_methods(["GET", "POST"])
def floor_edit(request, property_id, pk):
    prop = _get_property(request, property_id)
    floor = get_object_or_404(Floor, pk=pk, property=prop, tenant=request.tenant)
    form = FloorForm(request.POST or None, instance=floor)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Qavat yangilandi."))
        return redirect("properties:detail", pk=prop.pk)
    return render(
        request,
        "properties/simple_form.html",
        {
            "form": form,
            "title": _("Qavatni tahrirlash"),
            "property_obj": prop,
            "delete_url": reverse("properties:floor_delete", args=[prop.pk, floor.pk]),
            "delete_confirm": _("Bu qavatni o‘chirishni xohlaysizmi? Xonalar qavatsiz qoladi."),
        },
    )


@role_required(*PROPERTY_ADMIN)
@require_POST
def floor_delete(request, property_id, pk):
    prop = _get_property(request, property_id)
    floor = get_object_or_404(Floor, pk=pk, property=prop, tenant=request.tenant)
    floor.delete()
    messages.success(request, _("Qavat o‘chirildi."))
    return redirect("properties:detail", pk=prop.pk)


@role_required(*PROPERTY_ADMIN)
@require_http_methods(["GET", "POST"])
def rate_plan_edit(request, property_id, pk):
    prop = _get_property(request, property_id)
    rate = get_object_or_404(RatePlan, pk=pk, property=prop, tenant=request.tenant)
    form = RatePlanForm(request.POST or None, instance=rate, property_obj=prop)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Tarif yangilandi."))
        return redirect("properties:detail", pk=prop.pk)
    return render(
        request,
        "properties/simple_form.html",
        {
            "form": form,
            "title": _("Tarifni tahrirlash"),
            "property_obj": prop,
            "delete_url": reverse("properties:rate_plan_delete", args=[prop.pk, rate.pk]),
            "delete_confirm": _(
                "Bu tarifni o‘chirishni xohlaysizmi? Bog‘langan mavsumlar ham o‘chadi."
            ),
        },
    )


@role_required(*PROPERTY_ADMIN)
@require_POST
def rate_plan_delete(request, property_id, pk):
    prop = _get_property(request, property_id)
    rate = get_object_or_404(RatePlan, pk=pk, property=prop, tenant=request.tenant)
    rate.delete()
    messages.success(request, _("Tarif o‘chirildi."))
    return redirect("properties:detail", pk=prop.pk)


@feature_required("season_rates")
@role_required(*PROPERTY_ADMIN)
@require_http_methods(["GET", "POST"])
def rate_matrix(request, rate_id):
    from datetime import date, timedelta

    from django.utils import timezone

    rate = get_object_or_404(
        RatePlan.objects.select_related("property", "room_type"),
        pk=rate_id,
        tenant=request.tenant,
    )
    start_s = request.GET.get("start") or request.POST.get("start")
    start = timezone.localdate()
    if start_s:
        try:
            start = date.fromisoformat(start_s)
        except ValueError:
            pass
    form = SeasonRateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.tenant = request.tenant
        obj.rate_plan = rate
        obj.full_clean()
        obj.save()
        messages.success(request, _("Mavsum qo‘shildi / yangilandi."))
        return redirect(f"{request.path}?start={start.isoformat()}")
    matrix = build_rate_matrix(rate, start, days=42)
    return render(
        request,
        "properties/rate_matrix.html",
        {
            "rate": rate,
            "property_obj": rate.property,
            "matrix": matrix,
            "form": form,
            "start": start,
            "prev": start - timedelta(days=14),
            "next": start + timedelta(days=14),
            "seasons": rate.seasons.all(),
        },
    )


@role_required(*PROPERTY_ADMIN)
@require_http_methods(["GET", "POST"])
def season_create(request, rate_id):
    rate = get_object_or_404(RatePlan, pk=rate_id, tenant=request.tenant)
    form = SeasonRateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not request.tenant.has_feature("season_rates"):
            messages.error(request, _("Mavsumiy tarif Pro rejasida."))
            return redirect("properties:detail", pk=rate.property_id)
        obj = form.save(commit=False)
        obj.tenant = request.tenant
        obj.rate_plan = rate
        obj.full_clean()
        obj.save()
        messages.success(request, _("Mavsum qo‘shildi."))
        return redirect("properties:rate_matrix", rate_id=rate.pk)
    return render(
        request,
        "properties/simple_form.html",
        {"form": form, "title": _("Mavsum — %(name)s") % {"name": rate.name}, "property_obj": rate.property},
    )
