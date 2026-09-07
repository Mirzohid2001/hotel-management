from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from core.tests.helpers import make_plan, make_subscription, setup_tenant_user
from subscriptions.models import Plan, Subscription
from tenants.models import TenantMembership


class TenantMiddlewareTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(username="owner1")
        self.client = Client()

    def test_login_sets_tenant_on_request(self):
        self.client.login(username="owner1", password="pass12345")
        response = self.client.get(reverse("reports:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.ctx["tenant"].name)

    def test_tenant_switch(self):
        other = setup_tenant_user(username="owner1b")
        # same user on second tenant
        TenantMembership.objects.create(
            user=self.ctx["user"],
            tenant=other["tenant"],
            role=TenantMembership.Role.MANAGER,
            is_active=True,
        )
        self.client.login(username="owner1", password="pass12345")
        self.client.post(reverse("tenants:switch", args=[other["tenant"].pk]))
        response = self.client.get(reverse("reports:dashboard"))
        self.assertContains(response, other["tenant"].name)


class SubscriptionFeatureTests(TestCase):
    def test_pro_has_payroll_free_does_not(self):
        free_ctx = setup_tenant_user(plan_code=Plan.Code.FREE, username="freeuser")
        pro_ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="prouser")
        self.assertFalse(free_ctx["tenant"].has_feature("payroll"))
        self.assertTrue(pro_ctx["tenant"].has_feature("payroll"))

    def test_room_limit_free(self):
        ctx = setup_tenant_user(plan_code=Plan.Code.FREE, username="limituser")
        self.assertTrue(ctx["tenant"].check_limit("rooms", 0))
        self.assertTrue(ctx["tenant"].check_limit("rooms", 9))
        self.assertFalse(ctx["tenant"].check_limit("rooms", 10))

    def test_expired_subscription_blocks_dashboard(self):
        ctx = setup_tenant_user(username="expireduser")
        sub = ctx["subscription"]
        sub.period_end = timezone.localdate() - timedelta(days=1)
        sub.status = Subscription.Status.EXPIRED
        sub.save()
        client = Client()
        client.login(username="expireduser", password="pass12345")
        response = client.get(reverse("reports:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("subscriptions:expired"))

    def test_expired_page_accessible(self):
        ctx = setup_tenant_user(username="expired2")
        sub = ctx["subscription"]
        sub.period_end = timezone.localdate() - timedelta(days=1)
        sub.status = Subscription.Status.EXPIRED
        sub.save()
        client = Client()
        client.login(username="expired2", password="pass12345")
        response = client.get(reverse("subscriptions:expired"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Obuna")


class SubscriptionModelTests(TestCase):
    def test_is_currently_valid(self):
        plan = make_plan()
        ctx = setup_tenant_user(username="validuser")
        sub = ctx["subscription"]
        self.assertTrue(sub.is_currently_valid())
        sub.period_end = timezone.localdate() - timedelta(days=2)
        self.assertFalse(sub.is_currently_valid())

    def test_seed_plans_command(self):
        from django.core.management import call_command

        call_command("seed_plans")
        self.assertEqual(Plan.objects.count(), 3)
        free = Plan.objects.get(code=Plan.Code.FREE)
        self.assertIn("features", free.limits)
        self.assertEqual(free.limits["rooms"], 10)
