from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from bookings.services import check_in_reservation, create_reservation
from core.tests.helpers import setup_tenant_user
from guests.models import Guest
from inventory.models import StockItem
from inventory.services import sell_minibar
from maintenance.models import MaintenanceTicket
from maintenance.services import complete_ticket, open_ticket
from properties.models import Property, RatePlan, Room, RoomType
from reports.night_audit import run_night_audit
from reports.services import occupancy_stats
from services.models import ServiceItem
from services.services import order_service
from subscriptions.models import Plan


class OpsModulesTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="opsuser")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.prop = Property.objects.create(tenant=self.tenant, name="Ops Hotel")
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Std",
            code="std",
            base_price=Decimal("200000"),
        )
        self.room = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="301"
        )
        self.rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="BAR",
            code="bar",
            price=Decimal("200000"),
        )
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Guest")
        self.today = timezone.localdate()
        self.reservation = create_reservation(
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
        check_in_reservation(self.reservation, self.user)

    def test_service_order_posts_folio(self):
        service = ServiceItem.objects.create(
            tenant=self.tenant,
            name="Breakfast",
            code="bf",
            unit_price=Decimal("50000"),
        )
        order = order_service(
            reservation=self.reservation, service=service, user=self.user, quantity=2
        )
        self.assertEqual(order.amount, Decimal("100000"))
        self.assertEqual(self.reservation.folio.charges.filter(charge_type="service").count(), 1)

    def test_minibar_reduces_stock(self):
        item = StockItem.objects.create(
            tenant=self.tenant,
            hotel=self.prop,
            name="Cola",
            sku="cola",
            quantity_on_hand=Decimal("10"),
            sell_price=Decimal("15000"),
            is_minibar=True,
        )
        sell_minibar(reservation=self.reservation, item=item, user=self.user, quantity=2)
        item.refresh_from_db()
        self.assertEqual(item.quantity_on_hand, Decimal("8"))
        self.assertEqual(self.reservation.folio.charges.filter(charge_type="minibar").count(), 1)

    def test_maintenance_sets_ooo(self):
        ticket = MaintenanceTicket.objects.create(
            tenant=self.tenant,
            room=self.room,
            title="AC broken",
            set_room_ooo=True,
            created_by=self.user,
        )
        open_ticket(ticket)
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, Room.Status.OUT_OF_ORDER)
        complete_ticket(ticket, user=self.user)
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, Room.Status.DIRTY)

    def test_night_audit_posts_once(self):
        run = run_night_audit(self.tenant, self.user, audit_date=self.today, hotel=self.prop)
        self.assertGreaterEqual(run.posted_room_charges, 1)
        with self.assertRaises(ValidationError):
            run_night_audit(self.tenant, self.user, audit_date=self.today, hotel=self.prop)

    def test_occupancy_stats(self):
        stats = occupancy_stats(self.tenant, self.today)
        self.assertEqual(stats["occupied_rooms"], 1)
        self.assertGreaterEqual(stats["total_rooms"], 1)
