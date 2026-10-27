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

    def test_referrer_list_has_delete_and_hard_delete(self):
        ref = BookingReferrer.objects.create(
            tenant=self.tenant, name="Temp Agent", default_commission_percent=5
        )
        list_url = reverse("bookings:referrer_list")
        resp = self.client.get(list_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "O‘chirish")
        self.assertContains(resp, reverse("bookings:referrer_delete", args=[ref.pk]))

        resp = self.client.post(reverse("bookings:referrer_delete", args=[ref.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(BookingReferrer.objects.filter(pk=ref.pk).exists())

    def test_referrer_with_reservation_soft_deletes(self):
        from datetime import date, timedelta
        from decimal import Decimal

        from bookings.models import Reservation
        from core.tests.helpers import make_property_stack
        from guests.models import Guest

        stack = make_property_stack(self.tenant, name="H2")
        guest = Guest.objects.create(
            tenant=self.tenant, first_name="A", last_name="B", phone="900"
        )
        ref = BookingReferrer.objects.create(
            tenant=self.tenant, name="Linked", default_commission_percent=10
        )
        today = date.today()
        Reservation.objects.create(
            tenant=self.tenant,
            code="T-DEL-1",
            hotel=stack["property"],
            guest=guest,
            room=stack["room"],
            room_type=stack["room_type"],
            check_in=today,
            check_out=today + timedelta(days=1),
            referrer=ref,
            commission_percent=Decimal("10"),
            adults=1,
            status=Reservation.Status.CONFIRMED,
        )
        resp = self.client.post(reverse("bookings:referrer_delete", args=[ref.pk]))
        self.assertEqual(resp.status_code, 302)
        ref.refresh_from_db()
        self.assertFalse(ref.is_active)
