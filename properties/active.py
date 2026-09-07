from properties.models import Property

SESSION_PROPERTY_KEY = "active_property_id"
ALL_PROPERTIES = "all"


def membership_properties(membership):
    from tenants.property_access import membership_properties as _mp

    return _mp(membership)


def tenant_properties(tenant, membership=None):
    if tenant is None:
        return Property.objects.none()
    if membership is not None:
        return membership_properties(membership)
    return Property.objects.filter(tenant=tenant, is_active=True).order_by("name")


def resolve_active_property(request):
    """Session property, 'all' for consolidated view, or first allowed property."""
    tenant = getattr(request, "tenant", None)
    membership = getattr(request, "membership", None)
    props = tenant_properties(tenant, membership)
    if not props.exists():
        return None
    pid = request.session.get(SESSION_PROPERTY_KEY)
    if pid == ALL_PROPERTIES:
        if props.count() > 1:
            return None
        prop = props.first()
        request.session[SESSION_PROPERTY_KEY] = prop.pk
        return prop
    if pid:
        prop = props.filter(pk=pid).first()
        if prop:
            return prop
    prop = props.first()
    request.session[SESSION_PROPERTY_KEY] = prop.pk
    return prop


def property_scope_is_all(request) -> bool:
    return request.session.get(SESSION_PROPERTY_KEY) == ALL_PROPERTIES


def set_active_property(request, property_obj: Property) -> bool:
    membership = getattr(request, "membership", None)
    tenant = getattr(request, "tenant", None)
    if tenant is None or property_obj.tenant_id != tenant.id or not property_obj.is_active:
        return False
    from tenants.property_access import can_access_property

    if not can_access_property(membership, property_obj):
        return False
    request.session[SESSION_PROPERTY_KEY] = property_obj.pk
    request.active_property = property_obj
    return True


def set_all_properties(request) -> bool:
    membership = getattr(request, "membership", None)
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        return False
    if tenant_properties(tenant, membership).count() < 2:
        return False
    request.session[SESSION_PROPERTY_KEY] = ALL_PROPERTIES
    request.active_property = None
    return True


def clear_active_property(request):
    request.session.pop(SESSION_PROPERTY_KEY, None)
    request.active_property = None
