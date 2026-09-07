from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from core.htmx import oob_select_response
from core.mixins import feature_required, role_required
from core.roles import INVENTORY

from .forms import (
    MinibarItemQuickForm,
    MinibarQuickForm,
    MinibarSaleForm,
    StockAdjustForm,
    StockItemForm,
)
from .models import StockItem
from .services import (
    adjust_stock,
    expired_stock_items,
    expiring_soon_stock_items,
    low_stock_items,
    sell_minibar,
)


def _active_hotel(request):
    return getattr(request, "active_property", None)


def _unique_sku(tenant, hotel, base: str) -> str:
    base = (slugify(base) or "item")[:32]
    sku = base
    n = 2
    qs = StockItem.objects.filter(tenant=tenant, sku=sku)
    if hotel is not None:
        qs = qs.filter(hotel=hotel)
    while qs.exists():
        suffix = f"-{n}"
        sku = f"{base[: 40 - len(suffix)]}{suffix}"
        n += 1
        qs = StockItem.objects.filter(tenant=tenant, sku=sku)
        if hotel is not None:
            qs = qs.filter(hotel=hotel)
    return sku


@role_required(*INVENTORY)
@feature_required("inventory")
def stock_list(request):
    hotel = _active_hotel(request)
    items_qs = StockItem.objects.filter(tenant=request.tenant).select_related("hotel")
    if hotel is not None:
        items_qs = items_qs.filter(hotel=hotel)
    items = list(items_qs)
    low = list(low_stock_items(request.tenant, hotel=hotel))
    low_ids = {i.pk for i in low}
    expired = list(expired_stock_items(request.tenant, hotel=hotel))
    soon = list(expiring_soon_stock_items(request.tenant, hotel=hotel))
    expired_ids = {i.pk for i in expired}
    soon_ids = {i.pk for i in soon}

    def sort_key(item):
        status = item.expiry_status()
        rank = {"expired": 0, "soon": 1, "ok": 2, "none": 3}.get(status, 3)
        return (rank, item.expiry_date or date.max, item.name.lower())

    items.sort(key=sort_key)
    return render(
        request,
        "inventory/stock_list.html",
        {
            "items": items,
            "hotel": hotel,
            "low_ids": low_ids,
            "low_count": len(low),
            "expired_ids": expired_ids,
            "soon_ids": soon_ids,
            "expired_count": len(expired),
            "soon_count": len(soon),
        },
    )


@role_required(*INVENTORY)
@feature_required("inventory")
@require_http_methods(["GET", "POST"])
def stock_create(request):
    hotel = _active_hotel(request)
    if hotel is None:
        messages.error(request, _("Ombor uchun avval filial tanlang."))
        return redirect("inventory:list")
    form = StockItemForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.tenant = request.tenant
        obj.hotel = hotel
        obj.save()
        messages.success(request, _("Mahsulot qo‘shildi."))
        return redirect("inventory:list")
    return render(
        request,
        "inventory/stock_form.html",
        {"form": form, "title": _("Yangi mahsulot"), "hotel": hotel},
    )


@role_required(*INVENTORY)
@feature_required("inventory")
@require_http_methods(["GET", "POST"])
def stock_edit(request, pk):
    hotel = _active_hotel(request)
    item = get_object_or_404(StockItem, pk=pk, tenant=request.tenant)
    if hotel is not None and item.hotel_id and item.hotel_id != hotel.pk:
        messages.error(request, _("Bu mahsulot boshqa filial omboriga tegishli."))
        return redirect("inventory:list")
    form = StockItemForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Yangilandi."))
        return redirect("inventory:list")
    return render(
        request,
        "inventory/stock_form.html",
        {"form": form, "title": _("Mahsulotni tahrirlash"), "item": item, "hotel": hotel},
    )


@role_required(*INVENTORY)
@feature_required("inventory")
@require_http_methods(["GET", "POST"])
def stock_adjust(request, pk):
    hotel = _active_hotel(request)
    item = get_object_or_404(StockItem, pk=pk, tenant=request.tenant)
    if hotel is not None and item.hotel_id and item.hotel_id != hotel.pk:
        messages.error(request, _("Bu mahsulot boshqa filial omboriga tegishli."))
        return redirect("inventory:list")
    form = StockAdjustForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            adjust_stock(
                item,
                movement_type=form.cleaned_data["movement_type"],
                quantity=form.cleaned_data["quantity"],
                user=request.user,
                note=form.cleaned_data.get("note") or "",
            )
            messages.success(request, _("Ombor yangilandi."))
            return redirect("inventory:list")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    return render(
        request,
        "inventory/stock_adjust.html",
        {"form": form, "item": item},
    )


@role_required(*INVENTORY)
@feature_required("inventory")
@require_http_methods(["GET", "POST"])
def minibar_sale(request):
    hotel = _active_hotel(request)
    form = MinibarSaleForm(request.POST or None, tenant=request.tenant, hotel=hotel)
    if request.method == "POST" and form.is_valid():
        try:
            sell_minibar(
                reservation=form.cleaned_data["reservation"],
                item=form.cleaned_data["item"],
                user=request.user,
                quantity=form.cleaned_data["quantity"],
            )
            messages.success(request, _("Minibar sotildi."))
            return redirect("inventory:minibar")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    return render(request, "inventory/minibar_sale.html", {"form": form})


@role_required(*INVENTORY)
@feature_required("inventory")
@require_http_methods(["GET", "POST"])
def minibar_quick(request):
    hotel = _active_hotel(request)
    form = MinibarQuickForm(request.POST or None, tenant=request.tenant, hotel=hotel)
    if request.method == "POST" and form.is_valid():
        try:
            sell_minibar(
                reservation=form.cleaned_data["reservation"],
                item=form.cleaned_data["item"],
                user=request.user,
                quantity=form.cleaned_data["quantity"],
            )
            messages.success(request, _("Minibar sotildi."))
            return redirect("inventory:minibar_quick")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    return render(request, "inventory/minibar_quick.html", {"form": form, "hotel": hotel})


@role_required(*INVENTORY)
@feature_required("inventory")
@require_http_methods(["GET", "POST"])
def minibar_item_quick(request):
    """HTMX: minibar mahsulotini tez qo‘shish va selectni yangilash."""
    hotel = _active_hotel(request)
    if hotel is None:
        messages.error(request, _("Avval filial tanlang."))
        return redirect("inventory:list")
    select_id = request.GET.get("select_id") or request.POST.get("select_id") or "id_item"
    field_name = request.GET.get("field_name") or request.POST.get("field_name") or "item"
    form = MinibarItemQuickForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        sku = (form.cleaned_data.get("sku") or "").strip() or _unique_sku(
            request.tenant, hotel, form.cleaned_data["name"]
        )
        if StockItem.objects.filter(tenant=request.tenant, hotel=hotel, sku=sku).exists():
            form.add_error("sku", _("Bu SKU allaqachon mavjud."))
        else:
            qty = form.cleaned_data.get("quantity_on_hand")
            if qty is None:
                qty = Decimal("10")
            item = StockItem.objects.create(
                tenant=request.tenant,
                hotel=hotel,
                name=form.cleaned_data["name"].strip(),
                sku=sku,
                quantity_on_hand=qty,
                sell_price=form.cleaned_data["sell_price"],
                is_minibar=True,
                is_active=True,
            )
            qs = StockItem.objects.filter(
                tenant=request.tenant, hotel=hotel, is_active=True, is_minibar=True
            ).order_by("name")
            return oob_select_response(select_id, field_name, qs, item.pk, required=True)
    return render(
        request,
        "inventory/partials/quick_item_form.html",
        {
            "form": form,
            "select_id": select_id,
            "field_name": field_name,
            "title": _("Yangi minibar mahsuloti"),
        },
    )
