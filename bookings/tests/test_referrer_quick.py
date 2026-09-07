from django.test import TestCase
from django.urls import reverse

from bookings.models import BookingReferrer
from core.tests.helpers import setup_tenant_user
from properties.models import Property
from subscriptions.models import Plan


class ReferrerQuickCreateTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.FREE, username="refquick")
        self.tenant = self.ctx["tenant"]
        self.client.force_login(self.ctx["user"])
        Property.objects.create(tenant=self.tenant, name="H1")

    def test_quick_referrer_htmx(self):
        url = reverse("bookings:referrer_quick")
        resp = self.client.get(
            url,
            {"select_id": "id_referrer", "field_name": "referrer"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Yangi yo‘naltiruvchi")
        resp = self.client.post(
            url,
            {
                "select_id": "id_referrer",
                "field_name": "referrer",
                "name": "Vali",
                "phone": "90111",
                "default_commission_percent": "15",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        ref = BookingReferrer.objects.get(tenant=self.tenant, name="Vali")
        body = resp.content.decode()
        self.assertIn(f'value="{ref.pk}" selected', body)
        self.assertIn('id="id_referrer"', body)
        self.assertIn('id="id_commission_percent"', body)
        self.assertIn('value="15"', body)
