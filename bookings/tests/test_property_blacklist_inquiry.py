from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Reservation
from bookings.services import (
    check_in_reservation,
    confirm_inquiry,
    create_reservation,
)
from core.tests.helpers import setup_tenant_user
from guests.models import Guest
from properties.active import SESSION_PROPERTY_KEY, set_active_property
from properties.models import Property, PropertySettings, RatePlan, Room, RoomType
from subscriptions.models import Plan


class PropertyBlacklistInquiryTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="ops3")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        self.prop_a = Property.objects.create(tenant=self.tenant, name="Hotel A")
        self.prop_b = Property.objects.create(tenant=self.tenant, name="Hotel B")
        PropertySettings.objects.create(tenant=self.tenant, property=self.prop_a,
            require_id_on_checkin=False,
        )
        PropertySettings.objects.create(tenant=self.tenant, property=self.prop_b,
            require_id_on_checkin=False,
        )
        self.rt_a = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop_a,
            name="Std A",
            code="a",
            base_price=Decimal("100000"),
        )
        self.rt_b = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop_b,
            name="Std B",
            code="b",
            base_price=Decimal("100000"),
        )
        self.room_a = Room.objects.create(
            tenant=self.tenant, property=self.prop_a, room_type=self.rt_a, number="A1"
        )
        self.room_b = Room.objects.create(
            tenant=self.tenant, property=self.prop_b, room_type=self.rt_b, number="B1"
        )
        self.rate_a = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop_a,
            room_type=self.rt_a,
            name="BAR",
            code="bara",
            price=Decimal("100000"),
        )
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Ok")
        self.blocked = Guest.objects.create(
            tenant=self.tenant,
            first_name="Bad",
            is_blacklisted=True,
            blacklist_reason="No-pay",
        )
        self.today = timezone.localdate()

    def test_blacklist_blocks_create(self):
        with self.assertRaises(ValidationError) as ctx:
            create_reservation(
                tenant=self.tenant,
                user=self.user,
                property_obj=self.prop_a,
                guest=self.blocked,
                room_type=self.rt_a,
                room=self.room_a,
                rate_plan=self.rate_a,
                check_in=self.today,
                check_out=self.today + timedelta(days=1),
            )
        self.assertIn("qora ro", str(ctx.exception).lower())

    def test_inquiry_confirm_pipeline(self):
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop_a,
            guest=self.guest,
            room_type=self.rt_a,
            room=self.room_a,
            rate_plan=self.rate_a,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
            status=Reservation.Status.INQUIRY,
        )
        self.assertEqual(reservation.status, Reservation.Status.INQUIRY)
        confirm_inquiry(reservation, self.user)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CONFIRMED)
        resp = self.client.get(reverse("bookings:inquiries"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(resp.context["reservations"]), [])
        self.assertContains(resp, "So‘rov yo")

    def test_property_switch_filters_board(self):
        create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop_a,
            guest=self.guest,
            room_type=self.rt_a,
            room=self.room_a,
            rate_plan=self.rate_a,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
        )
        session = self.client.session
        session[SESSION_PROPERTY_KEY] = self.prop_b.pk
        session.save()
        resp = self.client.get(reverse("bookings:board"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "B1")
        self.assertNotContains(resp, ">A1<")

        switch = self.client.post(
            reverse("properties:switch", args=[self.prop_a.pk]),
            {"next": reverse("bookings:board")},
        )
        self.assertEqual(switch.status_code, 302)
        resp2 = self.client.get(reverse("bookings:board"))
        self.assertContains(resp2, "A1")
