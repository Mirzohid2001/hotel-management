from django.test import TestCase
from django.urls import reverse

from core.tests.helpers import setup_tenant_user
from guests.models import Company, Guest
from properties.models import Property
from subscriptions.models import Plan


class QuickCreateTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.FREE, username="quicku")
        self.tenant = self.ctx["tenant"]
        self.client.force_login(self.ctx["user"])
        Property.objects.create(tenant=self.tenant, name="H1")

    def test_quick_guest_htmx(self):
        url = reverse("guests:quick_guest")
        resp = self.client.get(
            url, {"select_id": "id_guest", "field_name": "guest"}, HTTP_HX_REQUEST="true"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Yangi mehmon")
        resp = self.client.post(
            url,
            {
                "select_id": "id_guest",
                "field_name": "guest",
                "first_name": "Ali",
                "last_name": "Valiyev",
                "phone": "99890",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        guest = Guest.objects.get(tenant=self.tenant, first_name="Ali")
        body = resp.content.decode()
        self.assertIn(f'value="{guest.pk}" selected', body)
        self.assertIn('id="id_guest"', body)

    def test_quick_company_htmx(self):
        url = reverse("guests:quick_company")
        resp = self.client.post(
            url,
            {
                "select_id": "id_company",
                "field_name": "company",
                "name": "Acme Soft",
                "phone": "11",
                "inn": "123",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        company = Company.objects.get(tenant=self.tenant, name="Acme Soft")
        body = resp.content.decode()
        self.assertIn(f'value="{company.pk}" selected', body)
        self.assertIn('id="id_company"', body)
