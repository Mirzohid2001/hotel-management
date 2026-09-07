from django.conf import settings
from django.shortcuts import redirect
from django.urls import Resolver404, resolve


class SubscriptionGateMiddleware:
    """Redirect hotel staff to expired page when subscription is not valid."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_lock(request):
            try:
                match = resolve(request.path_info)
                url_name = f"{match.namespace}:{match.url_name}" if match.namespace else match.url_name
            except Resolver404:
                url_name = None
            exempt = getattr(settings, "SUBSCRIPTION_LOCK_EXEMPT_URL_NAMES", set())
            if url_name not in exempt and not request.path.startswith("/admin/"):
                return redirect("subscriptions:expired")
        return self.get_response(request)

    def _should_lock(self, request) -> bool:
        if not getattr(request, "user", None) or not request.user.is_authenticated:
            return False
        if request.user.is_superuser and not getattr(request, "tenant", None):
            return False
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return False
        sub = tenant.get_active_subscription()
        if sub is None:
            # Also check latest subscription that might be expired but still "active" flag wrong
            latest = tenant.subscriptions.select_related("plan").order_by("-period_end").first()
            if latest is None:
                return True
            return not latest.is_currently_valid()
        return not sub.is_currently_valid()
