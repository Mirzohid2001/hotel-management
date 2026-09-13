from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Reservation
from bookings.services import create_reservation
from core.notifications import SESSION_KEY, build_notifications
from core.tests.helpers import make_property_stack, setup_tenant_user
from guests.models import Guest
from subscriptions.models import Plan


class NotificationDismissTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="notifyd")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        stack = make_property_stack(self.tenant, room_number="305")
        self.prop = stack["property"]
        self.guest = Guest.objects.create(
            tenant=self.tenant, first_name="Alina", last_name="Arstanova"
        )
        self.today = timezone.localdate()
        self.reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=stack["room_type"],
            room=stack["room"],
            rate_plan=stack["rate_plan"],
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
            nightly_rate=Decimal("200000"),
            status=Reservation.Status.CONFIRMED,
        )

    def test_arrival_alert_appears_until_opened(self):
        notes = build_notifications(self.tenant)
        arrivals = [i for i in notes["items"] if i["kind"] == "arrival"]
        self.assertTrue(any(i["pk"] == self.reservation.pk for i in arrivals))
        resp = self.client.get(reverse("reports:dashboard"))
        self.assertContains(resp, "kind-arrival")
        self.assertContains(resp, "notify-count")
        self.assertContains(resp, f"arrival:{self.reservation.pk}")

    def test_opening_notification_hides_it(self):
        key = f"arrival:{self.reservation.pk}"
        target = reverse("bookings:detail", args=[self.reservation.pk])
        resp = self.client.get(
            reverse("core:notify_open"),
            {"key": key, "next": target},
        )
        self.assertRedirects(resp, target)
        session = self.client.session
        today = self.today.isoformat()
        self.assertIn(key, session[SESSION_KEY][today])

        dash = self.client.get(reverse("reports:dashboard"))
        self.assertNotContains(dash, "notify-count")
        self.assertNotContains(dash, key)
        self.assertContains(dash, "Yangi ogohlantirish yo‘q")

    def test_dismiss_button_hides_without_leaving_if_next_is_current(self):
        key = f"arrival:{self.reservation.pk}"
        here = reverse("reports:dashboard")
        resp = self.client.post(
            reverse("core:notify_dismiss"),
            {"key": key, "next": here},
        )
        self.assertRedirects(resp, here)
        session = self.client.session
        dismissed = set(session[SESSION_KEY][self.today.isoformat()])
        notes = build_notifications(self.tenant, dismissed=dismissed)
        self.assertFalse(any(i["pk"] == self.reservation.pk for i in notes["items"]))

    def test_rejects_external_next_url(self):
        resp = self.client.get(
            reverse("core:notify_open"),
            {"key": "arrival:1", "next": "https://evil.example/phish"},
        )
        self.assertRedirects(resp, "/", fetch_redirect_response=False)
