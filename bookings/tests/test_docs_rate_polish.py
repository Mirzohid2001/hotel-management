from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Reservation
from bookings.services import (
    MissingGuestDocsError,
    check_in_reservation,
    create_reservation,
)
from core.tests.helpers import setup_tenant_user
from guests.models import Guest, GuestDocument
from properties.models import Property, PropertySettings, RatePlan, Room, RoomType, SeasonRate
from properties.services import build_rate_matrix, price_for_date
from subscriptions.models import Plan


class DocsGateAndRateMatrixTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="polish")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        self.prop = Property.objects.create(tenant=self.tenant, name="Polish Hotel")
        self.settings = PropertySettings.objects.create(
            tenant=self.tenant,
            property=self.prop,
            require_id_on_checkin=True,
        )
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
        self.rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="BAR",
            code="bar",
            price=Decimal("100000"),
        )
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Docs")
        self.today = timezone.localdate()

    def _res(self):
        return create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
        )

    def test_docs_gate_blocks_then_override(self):
        reservation = self._res()
        with self.assertRaises(MissingGuestDocsError):
            check_in_reservation(reservation, self.user)
        check_in_reservation(reservation, self.user, allow_no_docs=True)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CHECKED_IN)

    def test_docs_gate_passes_with_passport(self):
        reservation = self._res()
        GuestDocument.objects.create(
            tenant=self.tenant,
            guest=self.guest,
            doc_type=GuestDocument.DocType.PASSPORT,
            number="AA1234567",
        )
        check_in_reservation(reservation, self.user)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CHECKED_IN)

    def test_rate_matrix_and_season_price(self):
        SeasonRate.objects.create(
            tenant=self.tenant,
            rate_plan=self.rate,
            name="Peak",
            date_from=self.today,
            date_to=self.today + timedelta(days=6),
            price=Decimal("150000"),
        )
        self.assertEqual(price_for_date(self.rate, self.today), Decimal("150000"))
        matrix = build_rate_matrix(self.rate, self.today, days=7)
        self.assertEqual(len(matrix), 7)
        self.assertTrue(matrix[0]["is_season"])
        self.assertEqual(matrix[0]["price"], Decimal("150000"))
        resp = self.client.get(reverse("properties:rate_matrix", args=[self.rate.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Peak")

    def test_walk_in_form_grid(self):
        resp = self.client.get(reverse("bookings:walk_in"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "walkin-layout")
        self.assertContains(resp, "walkin-room-grid")
