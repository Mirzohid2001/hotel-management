from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from core.tests.helpers import setup_tenant_user
from folio.models import Folio, FolioCharge
from folio.services import ensure_folio_for_reservation
from guests.models import Guest
from properties.models import Property, RatePlan, Room, RoomType
from reports.operations import operations_kpis, revenue_trend, room_status_summary
from subscriptions.models import Plan


class DashboardOperationsTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="dashops")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.prop = Property.objects.create(tenant=self.tenant, name="Dash Hotel")
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Std",
            code="std",
            base_price=Decimal("100000"),
        )
        self.room = Room.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            number="101",
            status=Room.Status.DIRTY,
        )
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Test")
        self.today = timezone.localdate()

    def test_room_status_summary(self):
        rows = room_status_summary(self.tenant, hotel=self.prop)
        dirty = next(r for r in rows if r["status"] == Room.Status.DIRTY)
        self.assertEqual(dirty["count"], 1)

    def test_revenue_trend_returns_seven_days(self):
        rows = revenue_trend(self.tenant, self.today, hotel=self.prop)
        self.assertEqual(len(rows), 7)
        self.assertTrue(rows[-1]["is_today"])

    def test_revenue_trend_nets_refunds(self):
        from folio.models import GuestPayment
        from folio.services import ensure_folio_for_reservation
        from bookings.services import create_reservation, check_in_reservation

        rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="BAR",
            code="bar2",
            price=Decimal("100000"),
        )
        self.room.status = Room.Status.READY
        self.room.save(update_fields=["status"])
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
        )
        check_in_reservation(reservation, self.user)
        folio = ensure_folio_for_reservation(reservation)
        GuestPayment.objects.create(
            tenant=self.tenant,
            folio=folio,
            amount=Decimal("150000"),
            method=GuestPayment.Method.CASH,
            kind=GuestPayment.Kind.PAYMENT,
            received_by=self.user,
            currency="UZS",
        )
        GuestPayment.objects.create(
            tenant=self.tenant,
            folio=folio,
            amount=Decimal("50000"),
            method=GuestPayment.Method.CASH,
            kind=GuestPayment.Kind.REFUND,
            received_by=self.user,
            currency="UZS",
        )
        rows = revenue_trend(self.tenant, self.today, days=1, hotel=self.prop)
        self.assertEqual(rows[-1]["amount"], Decimal("100000"))

    def test_operations_kpis_open_folio_balance(self):
        from bookings.services import create_reservation, check_in_reservation

        rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="BAR",
            code="bar",
            price=Decimal("100000"),
        )
        self.room.status = Room.Status.READY
        self.room.save(update_fields=["status"])
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
        )
        check_in_reservation(reservation, self.user)
        folio = ensure_folio_for_reservation(reservation)
        FolioCharge.objects.create(
            tenant=self.tenant,
            folio=folio,
            charge_type=FolioCharge.ChargeType.ROOM,
            description="test",
            unit_price=Decimal("50000"),
            quantity=Decimal("1"),
            amount=Decimal("50000"),
            posted_by=self.user,
        )
        kpis = operations_kpis(self.tenant, self.today, hotel=self.prop)
        self.assertEqual(kpis["open_folio_count"], 1)
        # Check-in posts stay nights (2 × 100k) + test charge 50k
        self.assertEqual(kpis["open_folio_balance"], Decimal("250000"))
