from django.test import TestCase
from django.urls import reverse

from core.models import ActivityLog
from core.tests.helpers import make_membership, make_user, setup_tenant_user
from tenants.models import TenantMembership


class LoginRedirectTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(username="loginadmin")
        self.admin = self.ctx["user"]
        self.manager = make_user(username="loginmgr")
        make_membership(self.manager, self.ctx["tenant"], role=TenantMembership.Role.MANAGER)

    def test_admin_redirects_to_dashboard(self):
        resp = self.client.post(
            reverse("accounts:login"),
            {"username": "loginadmin", "password": "pass12345"},
        )
        self.assertRedirects(resp, reverse("reports:dashboard"))

    def test_manager_redirects_to_board(self):
        resp = self.client.post(
            reverse("accounts:login"),
            {"username": "loginmgr", "password": "pass12345"},
        )
        self.assertRedirects(resp, reverse("bookings:board"))

    def test_receptionist_redirects_to_board(self):
        recv = make_user(username="loginrecv")
        make_membership(
            recv, self.ctx["tenant"], role=TenantMembership.Role.RECEPTIONIST
        )
        resp = self.client.post(
            reverse("accounts:login"),
            {"username": "loginrecv", "password": "pass12345"},
        )
        self.assertRedirects(resp, reverse("bookings:board"))

    def test_housekeeper_redirects_to_hk(self):
        hk = make_user(username="loginhk")
        make_membership(hk, self.ctx["tenant"], role=TenantMembership.Role.HOUSEKEEPER)
        resp = self.client.post(
            reverse("accounts:login"),
            {"username": "loginhk", "password": "pass12345"},
        )
        self.assertRedirects(resp, reverse("housekeeping:board"))
