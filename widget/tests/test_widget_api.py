"""Veb-bron widget — API va admin."""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from bookings.models import Reservation
from core.models import ActivityLog
from core.notifications import build_notifications
from core.tests.helpers import make_property_stack, setup_tenant_user
from properties.models import Room
from subscriptions.models import Plan
from widget.models import WidgetConfig
from widget.services import room_type_availability


class WidgetAvailabilityTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="wgtav")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        stack = make_property_stack(self.tenant, room_number="401", base_price=Decimal("200000"))
        self.prop = stack["property"]
        self.rt = stack["room_type"]
        self.rate = stack["rate_plan"]
        self.config = WidgetConfig.objects.get(hotel=self.prop)
        self.config.is_enabled = True
        self.config.allowed_domains = "example.uz"
        self.config.save()
        self.today = timezone.localdate()

    def test_room_type_availability_shows_free(self):
        rows = room_type_availability(
            self.tenant,
            self.prop,
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
            adults=2,
        )
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["available"])
        self.assertEqual(rows[0]["available_count"], 1)

    def test_api_availability_json(self):
        url = reverse(
            "widget:api_availability",
            args=[self.tenant.slug, self.prop.branch_code],
        )
        resp = self.client.get(
            url,
            {
                "check_in": self.today.isoformat(),
                "check_out": (self.today + timedelta(days=1)).isoformat(),
                "adults": 2,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["room_types"][0]["available"])

    def test_api_disabled_when_widget_off(self):
        self.config.is_enabled = False
        self.config.save()
        url = reverse(
            "widget:api_availability",
            args=[self.tenant.slug, self.prop.branch_code],
        )
        resp = self.client.get(
            url,
            {
                "check_in": self.today.isoformat(),
                "check_out": (self.today + timedelta(days=1)).isoformat(),
            },
        )
        self.assertEqual(resp.status_code, 403)


class WidgetBookTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="wgtbk")
        self.tenant = self.ctx["tenant"]
        stack = make_property_stack(self.tenant, room_number="402", base_price=Decimal("300000"))
        self.prop = stack["property"]
        self.room = stack["room"]
        self.rt = stack["room_type"]
        self.config = WidgetConfig.objects.get(hotel=self.prop)
        self.config.is_enabled = True
        self.config.auto_assign_room = True
        self.config.auto_confirm = False
        self.config.save()
        self.today = timezone.localdate()
        self.check_out = self.today + timedelta(days=2)

    def test_api_book_creates_inquiry(self):
        url = reverse("widget:api_book", args=[self.tenant.slug, self.prop.branch_code])
        resp = self.client.post(
            url,
            data={
                "check_in": self.today.isoformat(),
                "check_out": self.check_out.isoformat(),
                "room_type_id": self.rt.pk,
                "first_name": "Web",
                "last_name": "Guest",
                "phone": "+998901112233",
                "email": "web@test.local",
                "adults": 2,
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        reservation = Reservation.objects.get(code=body["code"])
        self.assertEqual(reservation.source, Reservation.Source.WEBSITE)
        self.assertEqual(reservation.status, Reservation.Status.INQUIRY)
        self.assertEqual(reservation.room_id, self.room.pk)
        self.assertTrue(
            ActivityLog.objects.filter(tenant=self.tenant, action="web_booking").exists()
        )

    def test_api_book_unavailable_when_all_booked(self):
        from bookings.services import check_in_reservation, create_reservation
        from guests.models import Guest

        guest = Guest.objects.create(tenant=self.tenant, first_name="Block")
        other = create_reservation(
            tenant=self.tenant,
            user=None,
            property_obj=self.prop,
            guest=guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=stack_rate(self.tenant, self.prop, self.rt),
            check_in=self.today,
            check_out=self.check_out,
        )
        check_in_reservation(other, None)

        url = reverse("widget:api_book", args=[self.tenant.slug, self.prop.branch_code])
        resp = self.client.post(
            url,
            data={
                "check_in": self.today.isoformat(),
                "check_out": self.check_out.isoformat(),
                "room_type_id": self.rt.pk,
                "first_name": "Fail",
                "phone": "+998909998877",
                "adults": 2,
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["code"], "unavailable")

    def test_notification_includes_web_booking(self):
        from widget.services import create_web_booking

        create_web_booking(
            self.config,
            self.tenant,
            room_type_id=self.rt.pk,
            check_in=self.today,
            check_out=self.check_out,
            first_name="Notify",
            last_name="Test",
            phone="+998901234567",
            email="",
        )
        notes = build_notifications(self.tenant)
        kinds = [n["kind"] for n in notes["items"]]
        self.assertIn("web_booking", kinds)

    @override_settings(WIDGET_BASE_URL="https://pms.test")
    def test_widget_frame_renders(self):
        url = reverse(
            "widget:frame",
            args=[self.tenant.slug, self.prop.branch_code],
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "widget-form")
        self.assertContains(resp, "WIDGET_CONFIG")


def stack_rate(tenant, prop, rt):
    from properties.models import RatePlan

    return RatePlan.objects.filter(tenant=tenant, property=prop, room_type=rt).first()
