"""Hotel multi-role navigation and access."""

from django.test import TestCase
from django.urls import reverse

from core.tests.helpers import make_membership, make_user, setup_tenant_user
from subscriptions.models import Plan
from tenants.models import TenantMembership


class RoleNavTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="navadmin")
        self.tenant = self.ctx["tenant"]
        self.admin = self.ctx["user"]
        self.manager = make_user(username="navmgr")
        make_membership(self.manager, self.tenant, role=TenantMembership.Role.MANAGER)
        self.receptionist = make_user(username="navrecv")
        make_membership(
            self.receptionist, self.tenant, role=TenantMembership.Role.RECEPTIONIST
        )
        self.housekeeper = make_user(username="navhk")
        make_membership(
            self.housekeeper, self.tenant, role=TenantMembership.Role.HOUSEKEEPER
        )
        self.accountant = make_user(username="navacc")
        make_membership(
            self.accountant, self.tenant, role=TenantMembership.Role.ACCOUNTANT
        )

    def _dashboard(self, user):
        self.client.force_login(user)
        return self.client.get(reverse("reports:dashboard"))

    def test_admin_sees_admin_nav_links(self):
        resp = self._dashboard(self.admin)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse("tenants:staff_list"))
        self.assertContains(resp, reverse("reports:pnl"))
        self.assertContains(resp, reverse("reports:flash"))
        self.assertContains(resp, reverse("reports:audit_log"))

    def test_manager_sees_ops_and_finance_but_not_staff(self):
        resp = self._dashboard(self.manager)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, reverse("tenants:staff_list"))
        self.assertContains(resp, reverse("reports:pnl"))
        self.assertContains(resp, reverse("hr:employees"))
        self.assertContains(resp, reverse("bookings:board"))

    def test_receptionist_front_office_only(self):
        resp = self._dashboard(self.receptionist)
        self.assertContains(resp, reverse("bookings:board"))
        self.assertContains(resp, reverse("guests:list"))
        html = resp.content.decode()
        nav_end = html.find('class="sidebar-footer"')
        nav = html[:nav_end] if nav_end > 0 else html
        self.assertNotIn(reverse("reports:pnl"), nav)
        self.assertNotIn(reverse("hr:employees"), nav)
        self.assertNotIn(reverse("tenants:staff_list"), nav)

    def test_housekeeper_sees_hk_not_front_desk(self):
        resp = self._dashboard(self.housekeeper)
        self.assertContains(resp, reverse("housekeeping:board"))
        html = resp.content.decode()
        nav_end = html.find('class="sidebar-footer"')
        nav = html[:nav_end] if nav_end > 0 else html
        self.assertNotIn(reverse("bookings:walk_in"), nav)
        self.assertNotIn(reverse("reports:pnl"), nav)

    def test_accountant_sees_finance(self):
        resp = self._dashboard(self.accountant)
        self.assertContains(resp, reverse("reports:pnl"))
        self.assertContains(resp, reverse("finance:list"))
        self.assertNotContains(resp, reverse("tenants:staff_list"))

    def test_manager_cannot_open_staff_list(self):
        self.client.force_login(self.manager)
        resp = self.client.get(reverse("tenants:staff_list"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("reports:dashboard"))

    def test_admin_can_open_staff_list(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("tenants:staff_list"))
        self.assertEqual(resp.status_code, 200)

    def test_receptionist_cannot_open_pnl(self):
        self.client.force_login(self.receptionist)
        resp = self.client.get(reverse("reports:pnl"))
        self.assertEqual(resp.status_code, 302)
