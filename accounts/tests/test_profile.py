from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.tests.helpers import setup_tenant_user
from tenants.models import TenantMembership

User = get_user_model()


class ProfileEditDeleteTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(username="profuser")
        self.client = Client()
        self.client.login(username="profuser", password="pass12345")

    def test_profile_shows_edit_and_delete(self):
        resp = self.client.get(reverse("accounts:profile"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse("accounts:profile_edit"))
        self.assertContains(resp, reverse("accounts:profile_delete"))

    def test_profile_edit_updates_fields(self):
        resp = self.client.post(
            reverse("accounts:profile_edit"),
            {
                "first_name": "Jamshid",
                "last_name": "Admin",
                "email": "jamshid@example.com",
                "phone": "+998901112233",
                "new_password": "",
                "new_password_confirm": "",
            },
        )
        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(username="profuser")
        self.assertEqual(user.first_name, "Jamshid")
        self.assertEqual(user.email, "jamshid@example.com")
        self.assertEqual(user.phone, "+998901112233")

    def test_sole_admin_cannot_delete(self):
        resp = self.client.post(reverse("accounts:profile_delete"))
        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(username="profuser")
        self.assertTrue(user.is_active)
        self.assertTrue(
            TenantMembership.objects.filter(user=user, is_active=True).exists()
        )

    def test_admin_can_delete_when_another_admin_exists(self):
        other = User.objects.create_user(username="otheradmin", password="pass12345")
        TenantMembership.objects.create(
            user=other,
            tenant=self.ctx["tenant"],
            role=TenantMembership.Role.ADMIN,
            is_active=True,
        )
        resp = self.client.post(reverse("accounts:profile_delete"))
        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(username="profuser")
        self.assertFalse(user.is_active)
        self.assertFalse(
            TenantMembership.objects.filter(user=user, is_active=True).exists()
        )
