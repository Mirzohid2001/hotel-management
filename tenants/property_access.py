"""Filial (property) access for tenant staff."""

from properties.models import Property
from tenants.models import TenantMembership


def membership_properties(membership: TenantMembership | None):
    """Properties this membership may view/switch to."""
    if membership is None:
        return Property.objects.none()
    base = Property.objects.filter(tenant=membership.tenant, is_active=True).order_by("name")
    if membership.role == TenantMembership.Role.ADMIN:
        return base
    assigned = list(
        membership.property_assignments.values_list("property_id", flat=True)
    )
    if not assigned:
        return base
    return base.filter(pk__in=assigned)


def can_access_property(membership: TenantMembership | None, property_obj: Property) -> bool:
    if membership is None or property_obj is None:
        return False
    if property_obj.tenant_id != membership.tenant_id or not property_obj.is_active:
        return False
    return membership_properties(membership).filter(pk=property_obj.pk).exists()
