from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse

from core.roles import home_url_name
from tenants.models import TenantMembership


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
