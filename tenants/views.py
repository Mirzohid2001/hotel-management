from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST
from django.utils.translation import gettext as _

from core.mixins import role_required
from core.roles import STAFF_ADMIN
from tenants.models import TenantMembership

from .forms import StaffInviteForm, StaffRoleForm, save_membership_properties
from .middleware import set_current_tenant
from .models import Tenant

User = get_user_model()


@login_required
@require_POST
def switch_tenant(request, tenant_id):
    tenant = get_object_or_404(Tenant, pk=tenant_id, is_active=True)
    set_current_tenant(request, tenant)
    next_url = request.POST.get("next") or request.GET.get("next") or "/"
    return redirect(next_url)


@login_required
def no_access(request):
    if getattr(request, "tenant", None) is not None:
        return redirect("reports:dashboard")
    return render(request, "tenants/no_access.html")


@role_required(*STAFF_ADMIN)
def staff_list(request):
    members = (
        TenantMembership.objects.filter(tenant=request.tenant)
        .select_related("user")
        .prefetch_related("property_assignments__property")
        .order_by("role", "user__username")
    )
    return render(request, "tenants/staff_list.html", {"members": members})


@role_required(*STAFF_ADMIN)
@require_http_methods(["GET", "POST"])
def staff_invite(request):
    form = StaffInviteForm(request.POST or None, tenant=request.tenant)
    if request.method == "POST" and form.is_valid():
        if not request.tenant.check_limit(
            "users",
            TenantMembership.objects.filter(tenant=request.tenant, is_active=True).count(),
        ):
            messages.error(request, _("Tarif bo‘yicha xodimlar limiti tugagan."))
            return redirect("tenants:staff_list")
        username = form.cleaned_data["username"]
        with transaction.atomic():
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": form.cleaned_data.get("email") or "",
                    "first_name": form.cleaned_data.get("first_name") or "",
                    "last_name": form.cleaned_data.get("last_name") or "",
                },
            )
            if created:
                user.set_password(form.cleaned_data["password"])
                user.save()
            membership, mem_created = TenantMembership.objects.get_or_create(
                user=user,
                tenant=request.tenant,
                defaults={
                    "role": form.cleaned_data["role"],
                    "is_active": True,
                },
            )
            if not mem_created:
                membership.role = form.cleaned_data["role"]
                membership.is_active = True
                membership.save()
            if "properties" in form.cleaned_data:
                save_membership_properties(membership, form.cleaned_data["properties"])
        messages.success(request, _("Xodim qo‘shildi: %(username)s") % {"username": username})
        return redirect("tenants:staff_list")
    return render(request, "tenants/staff_form.html", {"form": form, "title": _("Xodim qo‘shish")})


@role_required(*STAFF_ADMIN)
@require_http_methods(["GET", "POST"])
def staff_edit(request, pk):
    membership = get_object_or_404(TenantMembership, pk=pk, tenant=request.tenant)
    form = StaffRoleForm(request.POST or None, instance=membership)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Rol yangilandi."))
        return redirect("tenants:staff_list")
    return render(
        request,
        "tenants/staff_form.html",
        {"form": form, "title": _("Tahrirlash: %(user)s") % {"user": membership.user.username}},
    )
