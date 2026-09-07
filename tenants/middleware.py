from .models import Tenant, TenantMembership
from core.roles import nav_permissions

SESSION_TENANT_KEY = "current_tenant_id"


def _get_membership(request):
    if not request.user.is_authenticated:
        return None
    tenant_id = request.session.get(SESSION_TENANT_KEY)
    qs = TenantMembership.objects.filter(user=request.user, is_active=True).select_related(
        "tenant"
    )
    if tenant_id:
        membership = qs.filter(tenant_id=tenant_id, tenant__is_active=True).first()
        if membership:
            return membership
    membership = qs.filter(tenant__is_active=True).order_by("tenant__name").first()
    if membership:
        request.session[SESSION_TENANT_KEY] = membership.tenant_id
    return membership


class TenantMiddleware:
    """Attach request.tenant, request.membership, and request.active_property."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        membership = _get_membership(request)
        request.membership = membership
        request.tenant = membership.tenant if membership else None
        request.active_property = None
        if request.tenant is not None:
            from properties.active import resolve_active_property

            request.active_property = resolve_active_property(request)
        return self.get_response(request)


def tenant_context(request):
    memberships = []
    features = set()
    subscription = None
    notifications = {"items": [], "count": 0}
    tenant = getattr(request, "tenant", None)
    active_property = getattr(request, "active_property", None)
    tenant_properties = []
    if getattr(request, "user", None) and request.user.is_authenticated:
        memberships = list(
            TenantMembership.objects.filter(user=request.user, is_active=True)
            .select_related("tenant")
            .order_by("tenant__name")
        )
    if tenant is not None:
        subscription = tenant.get_active_subscription()
        if subscription and subscription.is_currently_valid():
            features = set(subscription.plan.limits.get("features", []))
        from core.notifications import build_notifications
        from properties.active import property_scope_is_all, tenant_properties as list_properties

        tenant_properties = list(list_properties(tenant, request.membership))
        notifications = build_notifications(tenant, hotel=active_property)
    return {
        "current_tenant": tenant,
        "current_membership": getattr(request, "membership", None),
        "is_tenant_admin": (
            getattr(request, "membership", None) is not None
            and request.membership.role == TenantMembership.Role.ADMIN
        ),
        "nav_perms": nav_permissions(
            getattr(request, "membership", None).role
            if getattr(request, "membership", None)
            else None
        ),
        "current_property": active_property,
        "property_scope_all": property_scope_is_all(request) if tenant else False,
        "tenant_properties": tenant_properties,
        "user_memberships": memberships,
        "plan_features": features,
        "subscription": subscription,
        "notifications": notifications,
    }



def set_current_tenant(request, tenant: Tenant) -> bool:
    ok = TenantMembership.objects.filter(
        user=request.user, tenant=tenant, is_active=True, tenant__is_active=True
    ).exists()
    if ok:
        from properties.active import clear_active_property

        request.session[SESSION_TENANT_KEY] = tenant.pk
        request.tenant = tenant
        clear_active_property(request)
    return ok
