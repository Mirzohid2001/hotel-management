from django.utils.translation import gettext as _
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from core.mixins import feature_required, role_required
from core.roles import SERVICES

from .forms import ServiceItemForm, ServiceOrderForm
from .models import ServiceItem, ServiceOrder
from .services import order_service


@role_required(*SERVICES)
@feature_required("services")
def service_list(request):
    items = ServiceItem.objects.filter(tenant=request.tenant)
    orders = ServiceOrder.objects.filter(tenant=request.tenant).select_related(
        "service", "reservation"
    )[:50]
    return render(
        request,
        "services/service_list.html",
        {"items": items, "orders": orders},
    )


@role_required(*SERVICES)
@feature_required("services")
@require_http_methods(["GET", "POST"])
def service_create(request):
    form = ServiceItemForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.tenant = request.tenant
        obj.save()
        messages.success(request, _("Xizmat qo‘shildi."))
        return redirect("services:list")
    return render(request, "services/service_form.html", {"form": form, "title": _("Yangi xizmat")})


@role_required(*SERVICES)
@feature_required("services")
@require_http_methods(["GET", "POST"])
def service_edit(request, pk):
    item = get_object_or_404(ServiceItem, pk=pk, tenant=request.tenant)
    form = ServiceItemForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Xizmat yangilandi."))
        return redirect("services:list")
    return render(request, "services/service_form.html", {"form": form, "title": _("Tahrirlash")})


@role_required(*SERVICES)
@feature_required("services")
@require_http_methods(["GET", "POST"])
def service_order(request):
    form = ServiceOrderForm(request.POST or None, tenant=request.tenant)
    if request.method == "POST" and form.is_valid():
        try:
            order_service(
                reservation=form.cleaned_data["reservation"],
                service=form.cleaned_data["service"],
                user=request.user,
                quantity=form.cleaned_data["quantity"],
                note=form.cleaned_data.get("note") or "",
            )
            messages.success(request, _("Xizmat mehmon hisobiga yozildi."))
            return redirect("services:list")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    return render(request, "services/order_form.html", {"form": form})
