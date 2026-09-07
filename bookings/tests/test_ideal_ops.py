from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Reservation
from bookings.services import DirtyRoomError, check_in_reservation, create_reservation
from core.tests.helpers import setup_tenant_user
from folio.models import FolioCharge, GuestPayment
from folio.services import (
    add_charge,
    add_payment,
    open_cash_shift,
    void_charge,
    void_payment,
)
from guests.models import Guest
from housekeeping.services import set_room_status
from inventory.models import StockItem
from inventory.services import sell_minibar
from properties.models import Property, PropertySettings, RatePlan, Room, RoomType
from services.models import ServiceItem
from services.services import order_service
from subscriptions.models import Plan


class IdealOpsSprintTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="idealops")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        self.prop = Property.objects.create(tenant=self.tenant, name="Ideal Hotel")
        PropertySettings.objects.create(tenant=self.tenant, property=self.prop,
            require_id_on_checkin=False,
        )
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Std",
            code="std",
            base_price=Decimal("100000"),
        )
        self.room = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="501"
        )
        self.rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="BAR",
            code="bar",
            price=Decimal("100000"),
        )
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Ideal")
        self.today = timezone.localdate()
        open_cash_shift(self.tenant, self.user, Decimal("0"), hotel=self.prop)

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

    def test_dirty_checkin_blocked_unless_override(self):
        reservation = self._res()
        set_room_status(self.room, Room.Status.DIRTY, user=self.user, note="test")
        with self.assertRaises(DirtyRoomError):
            check_in_reservation(reservation, self.user)
        stay = check_in_reservation(reservation, self.user, allow_dirty=True)
        self.assertIsNotNone(stay)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CHECKED_IN)

    def test_cleaning_also_blocked(self):
        reservation = self._res()
        set_room_status(self.room, Room.Status.CLEANING, user=self.user, note="test")
        with self.assertRaises(DirtyRoomError):
            check_in_reservation(reservation, self.user)

    def test_board_has_quick_actions(self):
        reservation = self._res()
        resp = self.client.get(reverse("bookings:board"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Kirish")
        self.assertContains(resp, reverse("bookings:check_in", args=[reservation.pk]))
        self.assertContains(resp, "Darhol joylash")

    def test_void_charge_and_payment(self):
        reservation = self._res()
        check_in_reservation(reservation, self.user)
        folio = reservation.folio
        charge = add_charge(
            folio,
            self.user,
            charge_type=FolioCharge.ChargeType.OTHER,
            description="Extra towel",
            unit_price=Decimal("10000"),
        )
        pay = add_payment(
            folio, self.user, amount=Decimal("10000"), method=GuestPayment.Method.CARD
        )
        self.assertEqual(folio.balance, Decimal("0"))
        void_charge(charge, self.user, reason="Guest declined")
        self.assertEqual(folio.charges_total, Decimal("0"))
        self.assertLess(folio.balance, 0)  # overpaid until void payment
        void_payment(pay, self.user, reason="Reversed with charge")
        self.assertEqual(folio.balance, Decimal("0"))
        charge.refresh_from_db()
        self.assertTrue(charge.is_void)

    def test_cash_requires_open_shift_and_binds(self):
        # close the setUp shift by creating another tenant scenario: use existing open
        reservation = self._res()
        check_in_reservation(reservation, self.user)
        pay = add_payment(
            reservation.folio,
            self.user,
            amount=Decimal("5000"),
            method=GuestPayment.Method.CASH,
        )
        self.assertIsNotNone(pay.cash_shift_id)

        from folio.services import close_cash_shift, get_open_shift

        shift = get_open_shift(self.tenant, hotel=self.prop)
        close_cash_shift(shift, self.user, Decimal("5000"))
        with self.assertRaises(ValidationError) as ctx:
            add_payment(
                reservation.folio,
                self.user,
                amount=Decimal("1000"),
                method=GuestPayment.Method.CASH,
            )
        self.assertIn("kassa smena", str(ctx.exception).lower())

    def test_post_service_and_minibar_from_stay(self):
        reservation = self._res()
        check_in_reservation(reservation, self.user)
        svc = ServiceItem.objects.create(
            tenant=self.tenant, name="Laundry", code="lnd", unit_price=Decimal("25000")
        )
        order_service(reservation=reservation, service=svc, user=self.user, quantity=Decimal("1"))
        item = StockItem.objects.create(
            tenant=self.tenant,
            hotel=self.prop,
            name="Cola",
            sku="cola",
            quantity_on_hand=Decimal("10"),
            unit_cost=Decimal("5000"),
            sell_price=Decimal("15000"),
            is_minibar=True,
        )
        sell_minibar(reservation=reservation, item=item, user=self.user, quantity=Decimal("1"))
        folio = reservation.folio
        types = set(folio.charges.filter(is_void=False).values_list("charge_type", flat=True))
        self.assertIn(FolioCharge.ChargeType.SERVICE, types)
        self.assertIn(FolioCharge.ChargeType.MINIBAR, types)
        item.refresh_from_db()
        self.assertEqual(item.quantity_on_hand, Decimal("9"))
