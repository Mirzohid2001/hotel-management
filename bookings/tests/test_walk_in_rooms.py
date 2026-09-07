"""Walk-in — band xonalar ro'yxatda ko'rinadi, tanlash mumkin emas."""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.services import check_in_reservation, create_reservation
from core.tests.helpers import make_property_stack, setup_tenant_user
from guests.models import Guest
from properties.active import SESSION_PROPERTY_KEY
from subscriptions.models import Plan


class WalkInRoomAvailabilityTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="walkrooms")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        stack = make_property_stack(self.tenant, room_number="601", base_price=100000)
        self.prop = stack["property"]
        self.room_free = stack["room"]
        self.rt = stack["room_type"]
        self.rate = stack["rate_plan"]
        from properties.models import Room

        self.room_busy = Room.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            number="602",
        )
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Busy")
        self.today = timezone.localdate()
        busy_res = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room_busy,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
        )
        check_in_reservation(busy_res, self.user)
        session = self.client.session
        session[SESSION_PROPERTY_KEY] = self.prop.pk
        session.save()

    def test_walk_in_page_marks_occupied_room_as_band(self):
        resp = self.client.get(reverse("bookings:walk_in"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "602")
        self.assertContains(resp, "Band")
        self.assertContains(resp, "601")
        self.assertContains(resp, "ta xona band")

    def test_walk_in_post_rejects_occupied_room(self):
        resp = self.client.post(
            reverse("bookings:walk_in"),
            {
                "first_name": "Fail",
                "room": self.room_busy.pk,
                "nightly_rate": "100000",
                "nights": 1,
                "adults": 1,
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "band", status_code=200)

    def test_walk_in_post_allows_free_room(self):
        resp = self.client.post(
            reverse("bookings:walk_in"),
            {
                "first_name": "Ok",
                "room": self.room_free.pk,
                "nightly_rate": "100000",
                "nights": 1,
                "adults": 1,
            },
        )
        self.assertEqual(resp.status_code, 302)

    def test_nights_htmx_partial_updates_rooms(self):
        resp = self.client.get(
            reverse("bookings:walk_in_rooms"),
            {"nights": 1},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "602")
        self.assertContains(resp, "Band")
