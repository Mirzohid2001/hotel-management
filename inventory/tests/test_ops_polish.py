from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.services import check_in_reservation, create_reservation
from core.notifications import build_notifications
from core.tests.helpers import setup_tenant_user
from guests.models import Guest
from inventory.models import StockItem
from inventory.services import low_stock_items, sell_minibar
from maintenance.models import MaintenanceTicket
from maintenance.services import assign_ticket, complete_ticket, open_ticket
from properties.models import Property, PropertySettings, RatePlan, Room, RoomType
from subscriptions.models import Plan


class MaintenanceInventoryOpsTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="ops8")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        self.prop = Property.objects.create(tenant=self.tenant, name="Ops8 Hotel")
        PropertySettings.objects.create(
            tenant=self.tenant, property=self.prop, require_id_on_checkin=False
        )
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Std",
            code="std",
            base_price=Decimal("200000"),
        )
        self.room = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="801"
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

    def test_maintenance_assign_and_list(self):
        ticket = MaintenanceTicket.objects.create(
            tenant=self.tenant,
            room=self.room,
            title="Leak",
            created_by=self.user,
        )
        open_ticket(ticket)
        assign_ticket(ticket, self.user)
        ticket.refresh_from_db()
        self.assertEqual(ticket.assignee_id, self.user.pk)
        self.assertEqual(ticket.status, MaintenanceTicket.Status.IN_PROGRESS)
        resp = self.client.get(reverse("maintenance:list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Leak")

    def test_low_stock_notification(self):
        StockItem.objects.create(
            tenant=self.tenant,
            hotel=self.prop,
            name="Towel",
            sku="towel",
            quantity_on_hand=Decimal("2"),
            reorder_level=Decimal("5"),
        )
        self.assertEqual(low_stock_items(self.tenant).count(), 1)
        notes = build_notifications(self.tenant)
        kinds = [i["kind"] for i in notes["items"]]
        self.assertIn("stock", kinds)
        resp = self.client.get(reverse("inventory:list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Kam")

    def test_expiry_notifications_and_list_badges(self):
        from inventory.services import expired_stock_items, expiring_soon_stock_items

        StockItem.objects.create(
            tenant=self.tenant,
            hotel=self.prop,
            name="Milk",
            sku="milk",
            quantity_on_hand=Decimal("3"),
            expiry_date=self.today - timedelta(days=1),
            expiry_alert_days=7,
        )
        StockItem.objects.create(
            tenant=self.tenant,
            hotel=self.prop,
            name="Juice",
            sku="juice",
            quantity_on_hand=Decimal("5"),
            expiry_date=self.today + timedelta(days=3),
            expiry_alert_days=7,
        )
        StockItem.objects.create(
            tenant=self.tenant,
            hotel=self.prop,
            name="Soap",
            sku="soap",
            quantity_on_hand=Decimal("10"),
            expiry_date=self.today + timedelta(days=60),
            expiry_alert_days=7,
        )
        self.assertEqual(expired_stock_items(self.tenant).count(), 1)
        self.assertEqual(len(expiring_soon_stock_items(self.tenant)), 1)
        notes = build_notifications(self.tenant)
        kinds = [i["kind"] for i in notes["items"]]
        self.assertIn("stock_expired", kinds)
        self.assertIn("stock_expiring", kinds)
        resp = self.client.get(reverse("inventory:list"))
        self.assertContains(resp, "Muddati o‘tgan")
        self.assertContains(resp, "Muddat yaqin")
        self.assertContains(resp, "Milk")

    def test_minibar_blocks_expired_item(self):
        item = StockItem.objects.create(
            tenant=self.tenant,
            hotel=self.prop,
            name="Old water",
            sku="old-water",
            quantity_on_hand=Decimal("5"),
            sell_price=Decimal("10000"),
            is_minibar=True,
            expiry_date=self.today - timedelta(days=2),
        )
        with self.assertRaises(ValidationError):
            sell_minibar(reservation=self.reservation, item=item, user=self.user)

    def test_minibar_still_works(self):
        item = StockItem.objects.create(
            tenant=self.tenant,
            hotel=self.prop,
            name="Water",
            sku="water",
            quantity_on_hand=Decimal("5"),
            sell_price=Decimal("10000"),
            is_minibar=True,
        )
        sell_minibar(reservation=self.reservation, item=item, user=self.user)
        item.refresh_from_db()
        self.assertEqual(item.quantity_on_hand, Decimal("4"))
