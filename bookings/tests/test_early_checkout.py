from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from bookings.services import (
    assert_room_available,
    check_in_reservation,
    check_out_reservation,
    create_reservation,
)
from core.tests.helpers import setup_tenant_user
from folio.models import FolioCharge
from folio.services import add_payment, ensure_stay_nights_posted
from guests.models import Guest
from properties.models import Property, PropertySettings, RatePlan, Room, RoomType
from subscriptions.models import Plan


class EarlyCheckoutReleaseTests(TestCase):
    def setUp(self):
        ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="earlyout")
        self.tenant = ctx["tenant"]
        self.user = ctx["user"]
        self.prop = Property.objects.create(tenant=self.tenant, name="Early Hotel")
        PropertySettings.objects.create(
            tenant=self.tenant, property=self.prop, require_id_on_checkin=False
        )
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Std",
            code="std",
            base_price=Decimal("100000"),
        )
        self.room = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="16"
        )
        self.rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="BAR",
            code="bar",
            price=Decimal("100000"),
        )
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Early")
        self.today = timezone.localdate()

    def test_early_checkout_frees_remaining_nights(self):
        # 14→17 booked, guest leaves on the 16th: night of the 16th must be free.
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today - timedelta(days=2),
            check_out=self.today + timedelta(days=1),
        )
        check_in_reservation(reservation, self.user)
        ensure_stay_nights_posted(reservation, self.user)
        add_payment(
            reservation.folio,
            self.user,
            amount=reservation.folio.balance,
            method="card",
        )
        check_out_reservation(reservation, self.user)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, reservation.Status.CHECKED_OUT)
        self.assertEqual(reservation.check_out, self.today)
        unused = FolioCharge.objects.filter(
            folio=reservation.folio,
            description__startswith=f"Night {self.today.isoformat()}",
            is_void=False,
        )
        self.assertFalse(unused.exists())
        assert_room_available(self.room, self.today, self.today + timedelta(days=1))
        next_guest = Guest.objects.create(tenant=self.tenant, first_name="Next")
        create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=next_guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
        )

    def test_scheduled_checkout_day_does_not_shorten(self):
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today - timedelta(days=1),
            check_out=self.today,
        )
        check_in_reservation(reservation, self.user)
        ensure_stay_nights_posted(reservation, self.user)
        add_payment(reservation.folio, self.user, amount=reservation.folio.balance, method="card")
        scheduled = reservation.check_out
        check_out_reservation(reservation, self.user)
        reservation.refresh_from_db()
        self.assertEqual(reservation.check_out, scheduled)
