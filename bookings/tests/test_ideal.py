from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from bookings.models import Reservation
from bookings.services import (
    cancel_reservation,
    check_in_reservation,
    create_reservation,
    mark_no_show,
    transfer_room,
)
from core.tests.helpers import setup_tenant_user
from folio.models import FolioCharge
from guests.models import Guest
from properties.models import Property, PropertySettings, RatePlan, Room, RoomType
from subscriptions.models import Plan


class IdealFlowTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="ideal")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.prop = Property.objects.create(tenant=self.tenant, name="Ideal Hotel")
        PropertySettings.objects.create(
            tenant=self.tenant,
            property=self.prop,
            cancel_fee_percent=Decimal("20"),
            no_show_fee_percent=Decimal("100"),
            require_id_on_checkin=False,
        )
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Std",
            code="std",
            base_price=Decimal("100000"),
        )
        self.room1 = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="401"
        )
        self.room2 = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="402"
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

    def test_cancel_posts_fee(self):
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room1,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
        )
        cancel_reservation(reservation, self.user, reason="guest cancel")
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CANCELLED)
        fee = FolioCharge.objects.filter(
            folio__reservation=reservation, charge_type=FolioCharge.ChargeType.CANCEL
        ).first()
        self.assertIsNotNone(fee)
        self.assertEqual(fee.amount, Decimal("20000"))

    def test_no_show_no_penalty_refunds_payment(self):
        from folio.models import GuestPayment
        from folio.services import add_payment, ensure_folio_for_reservation

        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room1,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
        )
        folio = ensure_folio_for_reservation(reservation, allow_pre_checkin=True)
        add_payment(
            folio,
            self.user,
            amount=Decimal("100000"),
            method=GuestPayment.Method.CARD,
            note="Depozit",
        )
        mark_no_show(reservation, self.user)
        fee = FolioCharge.objects.filter(
            folio__reservation=reservation,
            charge_type=FolioCharge.ChargeType.PENALTY,
            is_void=False,
        ).first()
        self.assertIsNone(fee)
        folio.refresh_from_db()
        active_charges = folio.charges.filter(is_void=False).count()
        self.assertEqual(active_charges, 0)
        self.assertEqual(folio.payments_total, Decimal("0"))
        self.assertEqual(folio.balance, Decimal("0"))
        refund = folio.payments.filter(kind=GuestPayment.Kind.REFUND, is_void=False).first()
        self.assertIsNotNone(refund)
        self.assertEqual(refund.amount, Decimal("100000"))

    def test_clear_existing_no_show_penalties(self):
        from bookings.services import clear_existing_no_show_penalties
        from folio.services import add_charge, ensure_folio_for_reservation

        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room1,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
        )
        # Eski siyosat: jarima qo‘lda yozilgan, status no_show
        folio = ensure_folio_for_reservation(reservation, allow_pre_checkin=True)
        add_charge(
            folio,
            self.user,
            charge_type=FolioCharge.ChargeType.PENALTY,
            description="Kelmaganlik to‘lovi (100.00%)",
            unit_price=Decimal("100000"),
        )
        reservation.status = Reservation.Status.NO_SHOW
        reservation.save(update_fields=["status", "updated_at"])

        dry = clear_existing_no_show_penalties(tenant=self.tenant, dry_run=True)
        self.assertIn(reservation.code, dry["reservations"])
        clear_existing_no_show_penalties(
            tenant=self.tenant, user=self.user, dry_run=False
        )
        self.assertFalse(
            FolioCharge.objects.filter(
                folio=folio, is_void=False, charge_type=FolioCharge.ChargeType.PENALTY
            ).exists()
        )
        folio.refresh_from_db()
        self.assertEqual(folio.balance, Decimal("0"))

    def test_transfer_marks_old_dirty(self):
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room1,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
        )
        check_in_reservation(reservation, self.user)
        transfer_room(reservation, self.user, self.room2, reason="upgrade")
        reservation.refresh_from_db()
        self.room1.refresh_from_db()
        self.assertEqual(reservation.room_id, self.room2.pk)
        self.assertEqual(self.room1.status, Room.Status.DIRTY)
        self.assertTrue(self.room1.hk_tasks.exists())

    def test_transfer_swaps_room_type_and_rate(self):
        """Double → Twin: tur va BAR tarif yangilanadi."""
        twin_type = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Twin · Ikki alohida",
            code="twin",
            base_price=Decimal("120000"),
        )
        twin_rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=twin_type,
            name="BAR · Twin",
            code="bar-twin",
            price=Decimal("120000"),
            is_default=True,
        )
        twin_room = Room.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=twin_type,
            number="501",
        )

        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room1,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
            adults=2,
        )
        check_in_reservation(reservation, self.user)
        old_type = reservation.room_type_id
        transfer_room(
            reservation,
            self.user,
            twin_room,
            reason="Mehmon Twin so‘radi",
            update_rate=True,
        )
        reservation.refresh_from_db()
        self.assertEqual(reservation.room_id, twin_room.pk)
        self.assertEqual(reservation.room_type_id, twin_type.pk)
        self.assertNotEqual(reservation.room_type_id, old_type)
        self.assertEqual(reservation.rate_plan_id, twin_rate.pk)
        self.assertEqual(reservation.total_amount, Decimal("240000"))
        self.assertTrue(
            reservation.change_logs.filter(field="room_type").exists()
        )
