from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.services import check_in_reservation, create_reservation
from core.tests.helpers import setup_tenant_user
from folio.services import (
    add_payment,
    close_cash_shift,
    close_folio,
    expected_cash_in_shift,
    get_open_shift,
    open_cash_shift,
)
from guests.models import Guest
from housekeeping.services import set_room_status
from properties.models import Property, RatePlan, Room, RoomType
from subscriptions.models import Plan


class FolioAndHKTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="folioer")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        self.prop = Property.objects.create(tenant=self.tenant, name="F Hotel")
        self.rt = RoomType.objects.create(
            tenant=self.tenant, property=self.prop, name="Std", code="s", base_price=Decimal("100")
        )
        self.room = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="201"
        )
        self.rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="BAR",
            code="bar",
            price=Decimal("100000"),
        )
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Nodir")
        self.today = timezone.localdate()

    def test_check_in_opens_folio_and_payment_closes(self):
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
        folio = reservation.folio
        self.assertTrue(folio.is_open)
        from folio.services import ensure_stay_nights_posted

        ensure_stay_nights_posted(reservation, self.user)
        self.assertEqual(folio.charges_total, Decimal("100000"))
        add_payment(folio, self.user, amount=Decimal("100000"), method="card")
        self.assertEqual(folio.balance, Decimal("0"))
        close_folio(folio)
        folio.refresh_from_db()
        self.assertFalse(folio.is_open)

    def test_hk_status_log(self):
        set_room_status(self.room, Room.Status.DIRTY, user=self.user, note="after checkout")
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, Room.Status.DIRTY)
        self.assertEqual(self.room.status_logs.count(), 1)

    def test_cash_shift_open_close_with_variance(self):
        shift = open_cash_shift(self.tenant, self.user, Decimal("100000"), hotel=self.prop)
        self.assertTrue(shift.is_open)
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
        add_payment(reservation.folio, self.user, amount=Decimal("50000"))
        expected = expected_cash_in_shift(shift)
        self.assertEqual(expected, Decimal("150000"))
        closed = close_cash_shift(shift, self.user, Decimal("149000"), notes="short")
        self.assertEqual(closed.variance, Decimal("-1000"))
        self.assertIsNone(get_open_shift(self.tenant, hotel=self.prop))

    def test_folio_detail_shows_credit_not_negative_balance(self):
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
        add_payment(reservation.folio, self.user, amount=Decimal("50000"), method="card")

        resp = self.client.get(reverse("folio:detail", args=[reservation.pk]))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Sdachi qaytarish")
        self.assertContains(resp, "Ortgan")
        self.assertContains(resp, reverse("folio:refund", args=[reservation.folio.pk]))

    def test_refund_overpayment_clears_credit(self):
        from folio.models import GuestPayment
        from folio.services import refund_overpayment

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
        from folio.services import ensure_stay_nights_posted

        ensure_stay_nights_posted(reservation, self.user)
        folio = reservation.folio
        # Room 100000 + overpay to 150000 → credit 50000
        add_payment(folio, self.user, amount=Decimal("150000"), method="card")
        self.assertEqual(folio.credit_amount, Decimal("50000"))

        refund = refund_overpayment(
            folio,
            self.user,
            amount=Decimal("50000"),
            method=GuestPayment.Method.CARD,
        )
        self.assertEqual(refund.kind, GuestPayment.Kind.REFUND)
        folio.refresh_from_db()
        self.assertEqual(folio.credit_amount, Decimal("0"))
        self.assertEqual(folio.amount_due, Decimal("0"))
        self.assertEqual(folio.payments_total, Decimal("100000"))

        # Cannot refund when no credit
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            refund_overpayment(folio, self.user, amount=Decimal("1000"))

        # UI post
        add_payment(folio, self.user, amount=Decimal("20000"), method="card")
        self.assertEqual(folio.credit_amount, Decimal("20000"))
        resp = self.client.post(
            reverse("folio:refund", args=[folio.pk]),
            {
                "method": "card",
                "amount": "20000",
                "currency": "UZS",
                "note": "Sdachi",
            },
        )
        self.assertEqual(resp.status_code, 302)
        folio.refresh_from_db()
        self.assertEqual(folio.credit_amount, Decimal("0"))
