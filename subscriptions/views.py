from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def expired(request):
    tenant = getattr(request, "tenant", None)
    subscription = None
    if tenant:
        subscription = tenant.subscriptions.select_related("plan").order_by("-period_end").first()
    return render(
        request,
        "subscriptions/expired.html",
        {"tenant": tenant, "subscription": subscription},
    )
