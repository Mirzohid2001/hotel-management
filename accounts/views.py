from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST

from core.roles import home_url_name
from tenants.models import TenantMembership

from .forms import ProfileForm


class LoginView(DjangoLoginView):
    template_name = "accounts/login.html"

    def get_success_url(self):
        user = self.request.user
        if user.is_authenticated:
            membership = (
                TenantMembership.objects.filter(
                    user=user,
                    is_active=True,
                    tenant__is_active=True,
                )
                .order_by("tenant__name")
                .first()
            )
            if membership:
                return reverse(home_url_name(membership.role))
        return reverse("reports:dashboard")


@login_required
def profile(request):
    return render(request, "accounts/profile.html", {"user_obj": request.user})


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        if form.cleaned_data.get("new_password"):
            update_session_auth_hash(request, user)
        messages.success(request, _("Profil yangilandi."))
        return redirect("accounts:profile")
    return render(
        request,
        "accounts/profile_form.html",
        {
            "form": form,
            "title": _("Profilni tahrirlash"),
            "delete_url": reverse("accounts:profile_delete"),
            "delete_confirm": _(
                "Akkauntingiz o‘chirilsinmi? Tizimga kira olmaysiz. Bu amalni qaytarib bo‘lmaydi."
            ),
        },
    )


@login_required
@require_POST
def profile_delete(request):
    user = request.user
    membership = getattr(request, "membership", None)
    if membership and membership.role == TenantMembership.Role.ADMIN:
        other_admins = (
            TenantMembership.objects.filter(
                tenant_id=membership.tenant_id,
                role=TenantMembership.Role.ADMIN,
                is_active=True,
            )
            .exclude(user_id=user.pk)
            .exists()
        )
        if not other_admins and not user.is_superuser:
            messages.error(
                request,
                _("Yagona admin akkauntini o‘chirib bo‘lmaydi. Avval boshqa admin qo‘shing."),
            )
            return redirect("accounts:profile")

    TenantMembership.objects.filter(user=user).update(is_active=False)
    user.is_active = False
    user.save(update_fields=["is_active"])
    logout(request)
    messages.success(request, _("Akkaunt o‘chirildi."))
    return redirect("accounts:login")
