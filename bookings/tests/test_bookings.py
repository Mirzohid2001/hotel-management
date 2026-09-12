from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from bookings.models import Reservation
from bookings.services import (
    AvailabilityError,
    apply_amendment,
    check_in_reservation,
    check_out_reservation,
    create_reservation,
)
from core.tests.helpers import setup_tenant_user
from folio.models import GuestPayment
from guests.models import Guest
from properties.models import Property, RatePlan, Room, RoomType


class BookingFlowTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(username="booker")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.prop = Property.objects.create(tenant=self.tenant, name="Demo Hotel")
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Standard",
            code="std",
            base_price=Decimal("300000"),
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
            price=Decimal("300000"),
        )
        self.guest = Guest.objects.create(
            tenant=self.tenant, first_name="Ali", last_name="Karimov", phone="90111"
        )
        self.today = timezone.localdate()

    def test_overlap_blocked(self):
        create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
        )
        with self.assertRaises(AvailabilityError):
            create_reservation(
                tenant=self.tenant,
                user=self.user,
                property_obj=self.prop,
                guest=self.guest,
                room_type=self.rt,
                room=self.room,
                rate_plan=self.rate,
                check_in=self.today + timedelta(days=1),
                check_out=self.today + timedelta(days=3),
            )

    def test_same_day_turnover_allowed(self):
        """Checkout day is free: 18→20 then new guest from 20 is OK."""
        create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
        )
        next_guest = Guest.objects.create(
            tenant=self.tenant, first_name="Next", last_name="Guest", phone="90222"
        )
        second = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=next_guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today + timedelta(days=2),
            check_out=self.today + timedelta(days=4),
        )
        self.assertEqual(second.check_in, self.today + timedelta(days=2))
        self.assertEqual(second.nights, 2)

    def test_check_in_out_and_dirty(self):
        reservation = create_reservation(
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
        check_in_reservation(reservation, self.user)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CHECKED_IN)
        from folio.services import add_payment, ensure_stay_nights_posted

        ensure_stay_nights_posted(reservation, self.user)
        add_payment(
            reservation.folio,
            self.user,
            amount=reservation.folio.balance,
            method=GuestPayment.Method.CARD,
        )
        check_out_reservation(reservation, self.user)
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, Room.Status.DIRTY)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CHECKED_OUT)

    def test_amend_extends_and_logs(self):
        reservation = create_reservation(
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
        apply_amendment(
            reservation,
            self.user,
            {
                "check_in": self.today,
                "check_out": self.today + timedelta(days=3),
                "room": self.room,
                "nightly_rate": Decimal("300000"),
                "adults": 2,
                "children": 0,
                "reason": "guest asked",
            },
        )
        reservation.refresh_from_db()
        self.assertEqual(reservation.nights, 3)
        self.assertEqual(reservation.nightly_rate, Decimal("300000"))
        self.assertIsNone(reservation.rate_plan_id)
        self.assertEqual(reservation.total_amount, Decimal("900000"))
        self.assertTrue(reservation.change_logs.filter(field="check_out").exists())

    def test_manual_nightly_rate_sets_total(self):
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            nightly_rate=Decimal("250000"),
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
        )
        self.assertEqual(reservation.nightly_rate, Decimal("250000"))
        self.assertIsNone(reservation.rate_plan_id)
        self.assertEqual(reservation.total_amount, Decimal("500000"))
        from folio.services import night_amount_for

        self.assertEqual(night_amount_for(reservation, self.today), Decimal("250000"))

    def test_check_in_without_room_fails(self):
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=None,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
        )
        with self.assertRaises(ValidationError):
            check_in_reservation(reservation, self.user)
