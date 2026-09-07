from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.utils.translation import gettext as _
from functools import wraps


class TenantRequiredMixin(LoginRequiredMixin):
    """Require authenticated user with an active tenant membership."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if getattr(request, "tenant", None) is None:
            return redirect("tenants:no_access")
        return super().dispatch(request, *args, **kwargs)


class RoleRequiredMixin(TenantRequiredMixin, UserPassesTestMixin):
    allowed_roles: tuple[str, ...] = ()

    def test_func(self):
        membership = getattr(self.request, "membership", None)
        if membership is None:
            return False
        if not self.allowed_roles:
            return True
        return membership.role in self.allowed_roles


class FeatureRequiredMixin(TenantRequiredMixin):
    required_feature: str = ""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if getattr(request, "tenant", None) is None:
            return redirect("tenants:no_access")
        if self.required_feature and not request.tenant.has_feature(self.required_feature):
            messages.warning(request, _("Bu modul joriy tarifda yo‘q."))
            return redirect("reports:dashboard")
        return super(TenantRequiredMixin, self).dispatch(request, *args, **kwargs)


def tenant_login_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if getattr(request, "tenant", None) is None:
            return redirect("tenants:no_access")
        return view_func(request, *args, **kwargs)

    return _wrapped


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        @tenant_login_required
        def _wrapped(request, *args, **kwargs):
            membership = getattr(request, "membership", None)
            if roles and (membership is None or membership.role not in roles):
                messages.error(request, _("Ruxsat yetarli emas."))
                from core.roles import home_url_name

                target = home_url_name(membership.role if membership else None)
                # Avoid redirect loop if the denied page is already the home.
                if getattr(request.resolver_match, "view_name", None) == target:
                    raise PermissionDenied(_("Ruxsat yetarli emas."))
                return redirect(target)
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def feature_required(feature: str):
    def decorator(view_func):
        @wraps(view_func)
        @tenant_login_required
        def _wrapped(request, *args, **kwargs):
            if not request.tenant.has_feature(feature):
                messages.warning(request, _("Bu modul joriy tarifda yo‘q."))
                from core.roles import home_url_name

                membership = getattr(request, "membership", None)
                return redirect(home_url_name(membership.role if membership else None))
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
