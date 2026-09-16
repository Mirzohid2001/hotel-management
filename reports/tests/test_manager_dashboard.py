"""Phase 3 — menejer uchun operatsion dashboard (admin bo‘limlari yashirin)."""

from django.test import TestCase
from django.urls import reverse

from core.tests.helpers import make_membership, make_user, setup_tenant_user
from subscriptions.models import Plan
from tenants.models import TenantMembership


class ManagerDashboardTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="dashadm")
        self.tenant = self.ctx["tenant"]
        self.admin = self.ctx["user"]
        self.manager = make_user(username="dashmgr")
        make_membership(self.manager, self.tenant, role=TenantMembership.Role.MANAGER)

    def _dashboard(self, user):
        self.client.force_login(user)
        return self.client.get(reverse("reports:dashboard"))

    def test_admin_sees_finance_and_audit_sections(self):
        resp = self._dashboard(self.admin)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "7 kunlik tushum")
        self.assertContains(resp, "Kun yopish rejasi")
        self.assertContains(resp, reverse("reports:pnl"))

    def test_manager_cannot_open_dashboard(self):
        resp = self._dashboard(self.manager)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("bookings:board"))
