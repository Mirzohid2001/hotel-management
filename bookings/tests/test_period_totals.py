from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Reservation
from bookings.services import create_reservation
from bookings.totals import (
    default_month_bounds,
    period_booking_summary,
    reservations_in_period,
    sum_reservation_totals,
)
from core.currency import DEFAULT_RATES_TO_UZS
from core.tests.helpers import make_property_stack, setup_tenant_user
from guests.models import Guest
from properties.models import Room
from subscriptions.models import Plan


class PeriodBookingTotalsTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="periodsum")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        stack = make_property_stack(self.tenant, room_number="101")
        self.prop = stack["property"]
        self.rt = stack["room_type"]
        self.rate = stack["rate_plan"]
        self.room = stack["room"]
        self.room2 = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="102"
        )
        self.guest = Guest.objects.create(
            tenant=self.tenant, first_name="Ali", last_name="Valiyev"
        )
        self.today = timezone.localdate()
        self.month_start, self.month_end = default_month_bounds(self.today)

    def _book(self, room, check_in, nights, amount, *, status=Reservation.Status.CONFIRMED, currency="UZS"):
        return create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=room,
            nightly_rate=amount,
            currency=currency,
            check_in=check_in,
            check_out=check_in + timedelta(days=nights),
            status=status,
        )

    def test_sum_excludes_cancelled_and_outside_period(self):
        in_month = self._book(self.room, self.month_start, 2, Decimal("200000"))
        prev_start = self.month_start - timedelta(days=10)
        self._book(self.room2, prev_start, 2, Decimal("500000"))
        cancelled = self._book(
            self.room2,
            self.month_start + timedelta(days=5),
            1,
            Decimal("900000"),
            status=Reservation.Status.CANCELLED,
        )
        qs = Reservation.objects.filter(tenant=self.tenant)
        qs = reservations_in_period(qs, self.month_start, self.month_end)
        summary = period_booking_summary(self.tenant, qs)
        self.assertEqual(summary["count"], 1)
        self.assertEqual(summary["total"], in_month.total_amount)
        self.assertEqual(cancelled.total_amount, Decimal("900000"))

    def test_overlap_includes_stay_crossing_month_start(self):
        crossing = self._book(
            self.room,
            self.month_start - timedelta(days=2),
            4,
            Decimal("100000"),
        )
        qs = reservations_in_period(
            Reservation.objects.filter(tenant=self.tenant),
            self.month_start,
            self.month_end,
        )
        summary = period_booking_summary(self.tenant, qs)
        self.assertEqual(summary["count"], 1)
        self.assertEqual(summary["total"], crossing.total_amount)

    def test_usd_converts_to_base(self):
        res = self._book(
            self.room, self.month_start, 1, Decimal("100"), currency="USD"
        )
        expected = (Decimal("100") * DEFAULT_RATES_TO_UZS["USD"]).quantize(Decimal("0.01"))
        self.assertEqual(sum_reservation_totals(self.tenant, Reservation.objects.filter(pk=res.pk)), expected)

    def test_list_default_month_shows_period_total(self):
        self._book(self.room, self.month_start, 2, Decimal("250000"))
        resp = self.client.get(reverse("bookings:list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Davrdagi bronlar jami")
        self.assertContains(resp, "500 000")
        self.assertEqual(resp.context["booking_total"], Decimal("500000"))
        self.assertEqual(resp.context["date_from"], self.month_start.isoformat())
        self.assertEqual(resp.context["date_to"], self.month_end.isoformat())

    def test_list_custom_period_filters_sum(self):
        self._book(self.room, self.month_start, 2, Decimal("200000"))
        later = min(self.month_start + timedelta(days=10), self.month_end - timedelta(days=1))
        self._book(self.room2, later, 1, Decimal("300000"))
        resp = self.client.get(
            reverse("bookings:list"),
            {
                "date_from": later.isoformat(),
                "date_to": self.month_end.isoformat(),
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["booking_total"], Decimal("300000"))
        self.assertEqual(resp.context["booking_total_count"], 1)

    def test_calendar_shows_period_total(self):
        self._book(self.room, self.today, 2, Decimal("180000"))
        resp = self.client.get(
            reverse("bookings:calendar"),
            {"start": self.today.isoformat(), "view": "14"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Davrdagi bronlar jami")
        self.assertEqual(resp.context["booking_total"], Decimal("360000"))
        self.assertContains(resp, "360 000")
