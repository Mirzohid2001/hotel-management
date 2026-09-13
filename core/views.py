from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods, require_POST

from core.mixins import tenant_login_required
from core.notifications import dismiss_notification, safe_next_url


@tenant_login_required
@require_http_methods(["GET", "POST"])
def notify_open(request):
    """Mark a topbar alert as seen, then open its page."""
    key = request.POST.get("key") or request.GET.get("key") or ""
    nxt = request.POST.get("next") or request.GET.get("next")
    dismiss_notification(request, key)
    return redirect(safe_next_url(nxt, fallback="/", allowed_host=request.get_host()))


@tenant_login_required
@require_POST
def notify_dismiss(request):
    """Close an alert without leaving the current page."""
    dismiss_notification(request, request.POST.get("key") or "")
    referer = request.META.get("HTTP_REFERER", "")
    return redirect(
        safe_next_url(
            request.POST.get("next") or referer,
            fallback="/",
            allowed_host=request.get_host(),
        )
    )
