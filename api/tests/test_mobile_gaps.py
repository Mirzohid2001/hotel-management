from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Reservation
from bookings.services import create_reservation
from core.tests.helpers import setup_tenant_user
from guests.models import Guest
from properties.models import Property, PropertySettings, RatePlan, Room, RoomType
from subscriptions.models import Plan
from tenants.models import TenantMembership


class MobileGapApiTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="gapadmin")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.user.set_password("pass12345")
        self.user.save()
        TenantMembership.objects.filter(user=self.user, tenant=self.tenant).update(
            role=TenantMembership.Role.ADMIN
        )
        self.prop = Property.objects.create(
            tenant=self.tenant, name="A Hotel", branch_code="a"
        )
        self.prop2 = Property.objects.create(
            tenant=self.tenant, name="B Hotel", branch_code="b"
        )
        PropertySettings.objects.create(tenant=self.tenant, property=self.prop)
        PropertySettings.objects.create(tenant=self.tenant, property=self.prop2)
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Std",
            code="std",
            base_price=Decimal("100000"),
        )
        self.room = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="101"
        )
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Ali")
        self.today = timezone.localdate()
        self.client = Client()

    def _token(self):
        resp = self.client.post(
            reverse("api:login"),
            data='{"username":"gapadmin","password":"pass12345"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.json()["data"]["token"]

    def _auth(self, token, hotel=""):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
        if hotel:
            headers["HTTP_X_HOTEL_ID"] = hotel
        return headers

    def test_all_hotels_header_does_not_404(self):
        token = self._token()
        resp = self.client.get(reverse("api:board"), **self._auth(token, "all"))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["data"]["stats"]["total"], 1)
        me = self.client.get(reverse("api:me"), **self._auth(token, "all"))
        self.assertEqual(me.status_code, 200, me.content)
        self.assertIsNone(me.json()["data"]["hotel"])

    def test_purge_removes_only_that_booking(self):
        token = self._token()
        res = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
            adults=1,
        )
        other = Guest.objects.create(tenant=self.tenant, first_name="Keep")
        resp = self.client.post(
            reverse("api:reservation_purge", args=[res.pk]),
            data="{}",
            content_type="application/json",
            **self._auth(token, str(self.prop.pk)),
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(Reservation.objects.filter(pk=res.pk).exists())
        self.assertTrue(Guest.objects.filter(pk=self.guest.pk).exists())
        self.assertTrue(Room.objects.filter(pk=self.room.pk).exists())
        self.assertTrue(Guest.objects.filter(pk=other.pk).exists())

    def test_guest_with_history_is_kept(self):
        token = self._token()
        create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
            adults=1,
        )
        resp = self.client.post(
            reverse("api:guest_delete", args=[self.guest.pk]),
            data="{}",
            content_type="application/json",
            **self._auth(token, str(self.prop.pk)),
        )
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertTrue(Guest.objects.filter(pk=self.guest.pk).exists())

    def test_day_rate_and_widget(self):
        token = self._token()
        plan = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="Rack",
            code="rack",
            price=Decimal("100000"),
        )
        resp = self.client.post(
            reverse("api:rate_plan_set_day", args=[plan.pk]),
            data=f'{{"date":"{self.today.isoformat()}","price":"150000"}}',
            content_type="application/json",
            **self._auth(token, str(self.prop.pk)),
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        widget = self.client.get(
            reverse("api:widget_config"),
            **self._auth(token, str(self.prop.pk)),
        )
        self.assertEqual(widget.status_code, 200, widget.content)
        saved = self.client.post(
            reverse("api:widget_config"),
            data='{"is_enabled":true,"welcome_title":"Xush kelibsiz"}',
            content_type="application/json",
            **self._auth(token, str(self.prop.pk)),
        )
        self.assertEqual(saved.status_code, 200, saved.content)
        self.assertTrue(saved.json()["data"]["is_enabled"])
        self.assertIn("embed_iframe", saved.json()["data"])

    def test_setup_seed_and_room_delete(self):
        token = self._token()
        headers = {
            "content_type": "application/json",
            **self._auth(token, str(self.prop.pk)),
        }
        seeded = self.client.post(
            reverse("api:room_types_seed"),
            data='{"with_rates":true}',
            **headers,
        )
        self.assertEqual(seeded.status_code, 200, seeded.content)
        codes = set(
            RoomType.objects.filter(property=self.prop).values_list("code", flat=True)
        )
        self.assertTrue({"twin", "double", "triple"}.issubset(codes))

        spare = Room.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            number="999",
        )
        deleted = self.client.post(
            reverse("api:room_delete", args=[spare.pk]),
            data="{}",
            **headers,
        )
        self.assertEqual(deleted.status_code, 200, deleted.content)
        self.assertFalse(Room.objects.filter(pk=spare.pk).exists())

    def test_maintenance_statement_print(self):
        token = self._token()
        resp = self.client.get(
            reverse("api:maintenance_statement_print"),
            **self._auth(token, str(self.prop.pk)),
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()["data"]
        self.assertIn("pdf_base64", data)
        self.assertTrue(data["filename"].endswith(".pdf"))
