"""Full matrix: each hotel role × key URLs (allow / deny)."""

from django.test import TestCase
from django.urls import reverse

from core.roles import (
    ACCOUNTING,
    CASH,
    DASHBOARD,
    FINANCE,
    FRONT_OFFICE,
    HOUSEKEEPING,
    HR,
    INVENTORY,
    OPS_MANAGER,
    PROPERTY_ADMIN,
    SERVICES,
    STAFF_ADMIN,
    home_url_name,
    nav_permissions,
)
from core.tests.helpers import make_membership, make_user, setup_tenant_user
from subscriptions.models import Plan
from tenants.models import TenantMembership


class RoleMatrixTests(TestCase):
    ROLE_USERS = {
        "admin": TenantMembership.Role.ADMIN,
        "manager": TenantMembership.Role.MANAGER,
        "receptionist": TenantMembership.Role.RECEPTIONIST,
        "housekeeper": TenantMembership.Role.HOUSEKEEPER,
        "accountant": TenantMembership.Role.ACCOUNTANT,
        "hr": TenantMembership.Role.HR,
    }

    # url_name → roles that must get HTTP 200 (others expect 302 to dashboard)
    ALLOW = {
        "reports:dashboard": set(DASHBOARD),
        "bookings:board": set(FRONT_OFFICE),
        "guests:list": set(FRONT_OFFICE),
        "properties:list": set(PROPERTY_ADMIN),
        "housekeeping:board": set(HOUSEKEEPING),
        "services:list": set(SERVICES),
        "inventory:list": set(INVENTORY),
        "maintenance:list": set(OPS_MANAGER),
        "finance:list": set(FINANCE),
        "folio:cash_shift": set(CASH),
        "reports:pnl": set(ACCOUNTING),
        "finance:profit_share": set(FINANCE),
        "hr:employees": set(HR),
        "tenants:staff_list": set(STAFF_ADMIN),
        "folio:city_ledger": set(FINANCE),
        "bookings:commission_report": set(ACCOUNTING),
    }

    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="matrix_admin")
        self.tenant = self.ctx["tenant"]
        self.users = {"admin": self.ctx["user"]}
        for key, role in self.ROLE_USERS.items():
            if key == "admin":
                continue
            user = make_user(username=f"matrix_{key}")
            make_membership(user, self.tenant, role=role)
            self.users[key] = user

    def test_all_six_roles_exist(self):
        codes = {c.value for c in TenantMembership.Role}
        self.assertEqual(
            codes,
            {"admin", "manager", "receptionist", "housekeeper", "accountant", "hr"},
        )

    def test_nav_and_home_helpers(self):
        self.assertTrue(nav_permissions("admin")["staff"])
        self.assertFalse(nav_permissions("manager")["staff"])
        self.assertTrue(nav_permissions("receptionist")["front_office"])
        self.assertFalse(nav_permissions("receptionist")["pnl"])
        self.assertTrue(nav_permissions("housekeeper")["housekeeping"])
        self.assertFalse(nav_permissions("housekeeper")["front_office"])
        self.assertFalse(nav_permissions("housekeeper")["properties"])
        self.assertFalse(nav_permissions("housekeeper")["maintenance"])
        self.assertTrue(nav_permissions("accountant")["pnl"])
        self.assertTrue(nav_permissions("hr")["hr"])
        self.assertEqual(home_url_name("housekeeper"), "housekeeping:board")
        self.assertEqual(home_url_name("receptionist"), "bookings:board")
        self.assertEqual(home_url_name("accountant"), "reports:pnl")
        self.assertEqual(home_url_name("hr"), "hr:employees")

    def test_url_access_matrix(self):
        dash = reverse("reports:dashboard")
        for url_name, allowed_roles in self.ALLOW.items():
            url = reverse(url_name)
            for key, role in self.ROLE_USERS.items():
                self.client.force_login(self.users[key])
                resp = self.client.get(url)
                if role in allowed_roles:
                    self.assertEqual(
                        resp.status_code,
                        200,
                        f"{key} should access {url_name}, got {resp.status_code}",
                    )
                else:
                    self.assertEqual(
                        resp.status_code,
                        302,
                        f"{key} should be denied {url_name}",
                    )
                    # Denied users go to their role home (not always dashboard)
                    self.assertIn(resp.url, {dash, reverse(home_url_name(role))})
