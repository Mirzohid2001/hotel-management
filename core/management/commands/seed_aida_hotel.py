"""Aida Hotel (aida-hotel.uz) — veb-bron widget seed."""

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from properties.models import Property, PropertySettings, RatePlan, Room, RoomType
from subscriptions.models import Plan, Subscription
from tenants.models import Tenant, TenantMembership
from widget.models import WidgetConfig


class Command(BaseCommand):
    help = "Seed Aida Hotel tenant + widget for aida-hotel.uz"

    def handle(self, *args, **options):
        from django.core.management import call_command

        call_command("seed_plans")
        plan = Plan.objects.get(code=Plan.Code.PRO)
        today = timezone.localdate()

        tenant, _ = Tenant.objects.get_or_create(
            slug="aida-hotel",
            defaults={"name": "Aida Hotel", "currency": "UZS"},
        )
        tenant.name = "Aida Hotel"
        tenant.is_active = True
        tenant.save()

        Subscription.objects.update_or_create(
            tenant=tenant,
            defaults={
                "plan": plan,
                "period_start": today - timedelta(days=1),
                "period_end": today + timedelta(days=365),
                "status": Subscription.Status.ACTIVE,
                "billing_period": Subscription.BillingPeriod.YEARLY,
                "admin_notes": "Aida Hotel veb-sayt",
            },
        )

        user, created = User.objects.get_or_create(
            username="aida",
            defaults={
                "first_name": "Aida",
                "last_name": "Admin",
                "email": "admin@aida-hotel.uz",
            },
        )
        if created:
            user.set_password("demo12345")
            user.save()
        TenantMembership.objects.update_or_create(
            user=user,
            tenant=tenant,
            defaults={"role": TenantMembership.Role.ADMIN, "is_active": True},
        )

        prop, _ = Property.objects.get_or_create(
            tenant=tenant,
            name="Aida Hotel",
            defaults={
                "city": "Toshkent",
                "address": "Toshkent",
                "phone": "+998",
            },
        )
        PropertySettings.objects.update_or_create(
            tenant=tenant,
            property=prop,
            defaults={"tax_percent": "12", "require_id_on_checkin": False},
        )
        rt, _ = RoomType.objects.get_or_create(
            tenant=tenant,
            property=prop,
            code="standard",
            defaults={
                "name": "Standard",
                "base_price": Decimal("500000"),
                "capacity_adults": 2,
                "description": "Qulay standart xona",
            },
        )
        rt_deluxe, _ = RoomType.objects.get_or_create(
            tenant=tenant,
            property=prop,
            code="deluxe",
            defaults={
                "name": "Deluxe",
                "base_price": Decimal("750000"),
                "capacity_adults": 3,
                "description": "Keng deluxe xona",
            },
        )
        RatePlan.objects.update_or_create(
            tenant=tenant,
            property=prop,
            code="bar-std",
            defaults={
                "name": "BAR Standard",
                "room_type": rt,
                "price": Decimal("500000"),
                "is_default": True,
            },
        )
        RatePlan.objects.update_or_create(
            tenant=tenant,
            property=prop,
            code="bar-dlx",
            defaults={
                "name": "BAR Deluxe",
                "room_type": rt_deluxe,
                "price": Decimal("750000"),
                "is_default": True,
            },
        )
        for num in ("101", "102", "201", "202"):
            rt_use = rt if num.startswith("1") else rt_deluxe
            Room.objects.get_or_create(
                tenant=tenant,
                property=prop,
                number=num,
                defaults={"room_type": rt_use},
            )

        config, _ = WidgetConfig.objects.get_or_create(
            tenant=tenant,
            hotel=prop,
            defaults={"is_enabled": False},
        )
        config.is_enabled = True
        config.allowed_domains = "aida-hotel.uz\nwww.aida-hotel.uz"
        config.auto_confirm = False
        config.auto_assign_room = True
        config.welcome_title = "Aida Hotel"
        config.welcome_text = "Onlayn bron — band xonalar darhol ko‘rsatiladi"
        config.save()

        self.stdout.write(self.style.SUCCESS("Aida Hotel ready"))
        self.stdout.write(f"  Tenant slug: {tenant.slug}")
        self.stdout.write("  Login: aida / demo12345")
        self.stdout.write("  Domains: aida-hotel.uz")
        self.stdout.write("")
        self.stdout.write("Saytga qo‘ying (iframe):")
        self.stdout.write(config.embed_iframe_html)
