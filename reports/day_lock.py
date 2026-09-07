"""Enforce business-day lock after night audit (per filial)."""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from core.roles import DAY_LOCK_OVERRIDE
from tenants.models import TenantMembership


def is_day_locked(tenant, day, hotel=None) -> bool:
    from reports.models import NightAuditRun

    qs = NightAuditRun.objects.filter(tenant=tenant, audit_date=day)
    if hotel is not None:
        return qs.filter(hotel=hotel).exists()
    from properties.models import Property

    props = Property.objects.filter(tenant=tenant, is_active=True)
    if not props.exists():
        return False
    locked_count = qs.filter(hotel__in=props).values("hotel_id").distinct().count()
    return locked_count >= props.count()


def is_property_day_locked(tenant, day, hotel) -> bool:
    from reports.models import NightAuditRun

    return NightAuditRun.objects.filter(tenant=tenant, audit_date=day, hotel=hotel).exists()


def can_override_day_lock(tenant, user) -> bool:
    if user is None or not user.is_authenticated:
        return False
    membership = TenantMembership.objects.filter(
        tenant=tenant, user=user, is_active=True
    ).first()
    return membership is not None and membership.role in DAY_LOCK_OVERRIDE


def assert_day_open(tenant, day, user=None, hotel=None) -> None:
    locked = is_property_day_locked(tenant, day, hotel) if hotel else is_day_locked(tenant, day)
    if not locked:
        return
    if can_override_day_lock(tenant, user):
        return
    if hotel is not None:
        raise ValidationError(
            _("%(hotel)s — %(d)s kuni yopilgan. Admin ochishi mumkin.")
            % {"d": day, "hotel": hotel.name}
        )
    raise ValidationError(
        _("Ish kuni %(d)s kun yopishdan keyin yopilgan. Admin ochishi mumkin.") % {"d": day}
    )
