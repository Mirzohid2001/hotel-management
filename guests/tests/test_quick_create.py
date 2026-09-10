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
        self.assertContains(resp, "Pasport")
        self.assertContains(resp, "doc_number")
        resp = self.client.post(
            url,
            {
                "select_id": "id_guest",
                "field_name": "guest",
                "first_name": "Ali",
                "last_name": "Valiyev",
                "phone": "99890",
                "nationality": "UZ",
                "doc_type": "passport",
                "doc_number": "AA1234567",
                "issued_country": "UZ",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        guest = Guest.objects.get(tenant=self.tenant, first_name="Ali")
        self.assertEqual(guest.nationality, "UZ")
        self.assertTrue(guest.documents.filter(number="AA1234567", doc_type="passport").exists())
        body = resp.content.decode()
        self.assertIn(f'value="{guest.pk}" selected', body)
        self.assertIn('id="id_guest"', body)

    def test_quick_guest_requires_passport(self):
        url = reverse("guests:quick_guest")
        resp = self.client.post(
            url,
            {
                "select_id": "id_guest",
                "field_name": "guest",
                "first_name": "NoDoc",
                "doc_type": "passport",
                "doc_number": "",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Guest.objects.filter(tenant=self.tenant, first_name="NoDoc").exists())
        self.assertContains(resp, "Pasport / ID raqami")
        self.assertContains(resp, "field-error")

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
