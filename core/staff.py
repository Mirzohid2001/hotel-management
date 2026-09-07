"""Tenant staff helpers."""

from django.contrib.auth import get_user_model

User = get_user_model()


def tenant_staff_users(tenant):
    """Active users with membership in this tenant (any role)."""
    return (
        User.objects.filter(
            memberships__tenant=tenant,
            memberships__is_active=True,
            is_active=True,
        )
        .distinct()
        .order_by("first_name", "username")
    )
