"""Shared test helpers for multi-tenant setup."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from subscriptions.models import DEFAULT_PLAN_LIMITS, Plan, Subscription
from tenants.models import Tenant, TenantMembership

User = get_user_model()


def make_plan(code=Plan.Code.PRO, **overrides):
    defaults = {
        "name": code.label if hasattr(code, "label") else code,
        "price_monthly": Decimal("0"),
        "price_yearly": Decimal("0"),
        "limits": DEFAULT_PLAN_LIMITS.get(code, DEFAULT_PLAN_LIMITS["pro"]).copy(),
        "is_active": True,
    }
    defaults.update(overrides)
    plan, _ = Plan.objects.get_or_create(code=code, defaults=defaults)
    if overrides:
        for k, v in overrides.items():
            setattr(plan, k, v)
        plan.save()
    return plan


def make_tenant(name="Test Hotel", **overrides):
    data = {"name": name, "is_active": True}
    data.update(overrides)
    return Tenant.objects.create(**data)


def make_user(username="staff", password="pass12345", **overrides):
    return User.objects.create_user(username=username, password=password, **overrides)


def make_membership(user, tenant, role=TenantMembership.Role.ADMIN):
    return TenantMembership.objects.create(
        user=user, tenant=tenant, role=role, is_active=True
    )


def make_subscription(tenant, plan=None, *, days=30, status=Subscription.Status.ACTIVE):
    plan = plan or make_plan()
    today = timezone.localdate()
    return Subscription.objects.create(
        tenant=tenant,
        plan=plan,
        period_start=today - timedelta(days=1),
        period_end=today + timedelta(days=days),
        status=status,
        billing_period=Subscription.BillingPeriod.MONTHLY,
    )


def setup_tenant_user(*, plan_code=Plan.Code.PRO, role=TenantMembership.Role.ADMIN, username="staff"):
    plan = make_plan(plan_code)
    tenant = make_tenant(name=f"Hotel {username}")
    user = make_user(username=username)
    membership = make_membership(user, tenant, role=role)
    subscription = make_subscription(tenant, plan)
    return {
        "plan": plan,
        "tenant": tenant,
        "user": user,
        "membership": membership,
        "subscription": subscription,
    }


def make_property_stack(
    tenant,
    *,
    name="Test Hotel",
    room_number="101",
    base_price=Decimal("100000"),
    room_status=None,
):
    """Property + room type + room + rate plan for integration tests."""
    from properties.models import Property, PropertySettings, RatePlan, Room, RoomType

    prop = Property.objects.create(tenant=tenant, name=name)
    PropertySettings.objects.create(
        tenant=tenant,
        property=prop,
        require_id_on_checkin=False,
    )
    rt = RoomType.objects.create(
        tenant=tenant,
        property=prop,
        name="Std",
        code="std",
        base_price=base_price,
    )
    room = Room.objects.create(
        tenant=tenant,
        property=prop,
        room_type=rt,
        number=room_number,
        status=room_status or Room.Status.READY,
    )
    rate = RatePlan.objects.create(
        tenant=tenant,
        property=prop,
        room_type=rt,
        name="BAR",
        code="bar",
        price=base_price,
    )
    return {
        "property": prop,
        "room_type": rt,
        "room": room,
        "rate_plan": rate,
    }
