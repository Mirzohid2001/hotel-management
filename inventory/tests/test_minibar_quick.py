"""Sprint 5 — minibar tez sotuv (xona raqami)."""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.services import check_in_reservation, create_reservation
from core.tests.helpers import make_property_stack, setup_tenant_user
from folio.models import FolioCharge
from guests.models import Guest
from inventory.models import StockItem
from properties.models import Room
from subscriptions.models import Plan


class MinibarQuickTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="mbquick")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        stack = make_property_stack(self.tenant, room_number="701")
        self.prop = stack["property"]
        self.room = stack["room"]
        self.rt = stack["room_type"]
        self.rate = stack["rate_plan"]
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Mini")
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
        self.item = StockItem.objects.create(
            tenant=self.tenant,
            hotel=self.prop,
            name="Suv",
            sku="water-q",
            quantity_on_hand=Decimal("10"),
            sell_price=Decimal("15000"),
            is_minibar=True,
        )

    def test_minibar_quick_page_loads(self):
        resp = self.client.get(reverse("inventory:minibar_quick"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Minibar tez")

    def test_minibar_quick_sells_by_room_number(self):
        resp = self.client.post(
            reverse("inventory:minibar_quick"),
            {
                "room_number": self.room.number,
                "item": self.item.pk,
                "quantity": "2",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity_on_hand, Decimal("8"))
        folio = self.reservation.folio
        charge = folio.charges.filter(charge_type=FolioCharge.ChargeType.MINIBAR).first()
        self.assertIsNotNone(charge)
        self.assertEqual(charge.amount, Decimal("30000"))

    def test_minibar_quick_unknown_room_fails(self):
        resp = self.client.post(
            reverse("inventory:minibar_quick"),
            {"room_number": "9999", "item": self.item.pk, "quantity": "1"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Xona topilmadi")
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity_on_hand, Decimal("10"))

    def test_minibar_quick_vacant_room_fails(self):
        empty_room = Room.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            number="703",
        )
        resp = self.client.post(
            reverse("inventory:minibar_quick"),
            {
                "room_number": empty_room.number,
                "item": self.item.pk,
                "quantity": "1",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "yashovchi mehmon")

    def test_quick_page_has_add_product_button(self):
        resp = self.client.get(reverse("inventory:minibar_quick"))
        self.assertContains(resp, reverse("inventory:quick_item"))
        self.assertContains(resp, "+ Yangi")

    def test_quick_item_htmx_creates_minibar_product(self):
        url = reverse("inventory:quick_item")
        resp = self.client.get(
            url,
            {"select_id": "id_item", "field_name": "item"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Yangi minibar")
        resp = self.client.post(
            url,
            {
                "select_id": "id_item",
                "field_name": "item",
                "name": "Pepsi 0.5",
                "sell_price": "12000",
                "quantity_on_hand": "20",
                "sku": "",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        item = StockItem.objects.get(tenant=self.tenant, name="Pepsi 0.5")
        self.assertTrue(item.is_minibar)
        self.assertEqual(item.sell_price, Decimal("12000"))
        self.assertTrue(item.sku)
        body = resp.content.decode()
        self.assertIn(f'value="{item.pk}" selected', body)
        self.assertIn('id="id_item"', body)
