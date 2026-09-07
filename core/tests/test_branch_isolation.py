"""Filial (Property) bo‘yicha ombor / kassa / rasxod izolyatsiyasi."""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.services import check_in_reservation, create_reservation
from core.notifications import build_notifications
from core.tests.helpers import make_property_stack, setup_tenant_user
from finance.models import Expense, ExpenseCategory
from folio.services import get_open_shift, open_cash_shift
from guests.models import Guest
from inventory.models import StockItem
from inventory.services import low_stock_items, sell_minibar
from properties.active import SESSION_PROPERTY_KEY
from properties.models import Property
from reports.accounting import build_pnl_report, expenses_in_range
from subscriptions.models import Plan


class BranchStockCashExpenseIsolationTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="branchiso")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)

        stack_a = make_property_stack(self.tenant, name="Filial A", room_number="A1")
        stack_b = make_property_stack(self.tenant, name="Filial B", room_number="B1")
        self.prop_a = stack_a["property"]
        self.prop_b = stack_b["property"]
        self.room_a = stack_a["room"]
        self.rt_a = stack_a["room_type"]
        self.rate_a = stack_a["rate_plan"]

        self.item_a = StockItem.objects.create(
            tenant=self.tenant,
            hotel=self.prop_a,
            name="Cola A",
            sku="cola",
            quantity_on_hand=Decimal("2"),
            reorder_level=Decimal("5"),
            sell_price=Decimal("15000"),
            is_minibar=True,
        )
        self.item_b = StockItem.objects.create(
            tenant=self.tenant,
            hotel=self.prop_b,
            name="Cola B",
            sku="cola",
            quantity_on_hand=Decimal("50"),
            reorder_level=Decimal("5"),
            sell_price=Decimal("15000"),
            is_minibar=True,
        )
        self.cat = ExpenseCategory.objects.create(tenant=self.tenant, name="Ops")
        self.today = timezone.localdate()
        self.exp_a = Expense.objects.create(
            tenant=self.tenant,
            hotel=self.prop_a,
            category=self.cat,
            title="Gaz A",
            amount=Decimal("100000"),
            expense_date=self.today,
            status=Expense.Status.PAID,
        )
        self.exp_b = Expense.objects.create(
            tenant=self.tenant,
            hotel=self.prop_b,
            category=self.cat,
            title="Gaz B",
            amount=Decimal("900000"),
            expense_date=self.today,
            status=Expense.Status.PAID,
        )

    def _activate(self, prop: Property):
        session = self.client.session
        session[SESSION_PROPERTY_KEY] = prop.pk
        session.save()

    def test_same_sku_allowed_per_branch(self):
        self.assertEqual(self.item_a.sku, self.item_b.sku)
        self.assertNotEqual(self.item_a.hotel_id, self.item_b.hotel_id)

    def test_low_stock_and_notifications_scoped(self):
        self.assertEqual(low_stock_items(self.tenant, hotel=self.prop_a).count(), 1)
        self.assertEqual(low_stock_items(self.tenant, hotel=self.prop_b).count(), 0)
        notes_a = build_notifications(self.tenant, hotel=self.prop_a)
        titles = [n["title"] for n in notes_a["items"] if n["kind"] == "stock"]
        self.assertTrue(any("Cola A" in t for t in titles))
        self.assertFalse(any("Cola B" in t for t in titles))

    def test_cash_shifts_independent_per_branch(self):
        open_cash_shift(self.tenant, self.user, Decimal("1000"), hotel=self.prop_a)
        open_cash_shift(self.tenant, self.user, Decimal("2000"), hotel=self.prop_b)
        a = get_open_shift(self.tenant, hotel=self.prop_a)
        b = get_open_shift(self.tenant, hotel=self.prop_b)
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertNotEqual(a.pk, b.pk)
        self.assertEqual(a.opening_float, Decimal("1000"))
        self.assertEqual(b.opening_float, Decimal("2000"))
        with self.assertRaises(ValidationError):
            open_cash_shift(self.tenant, self.user, Decimal("0"), hotel=self.prop_a)
        with self.assertRaises(ValidationError):
            open_cash_shift(self.tenant, self.user, Decimal("0"))

    def test_expenses_and_pnl_scoped_by_hotel(self):
        self.assertEqual(
            expenses_in_range(self.tenant, self.today, self.today, hotel=self.prop_a),
            Decimal("100000"),
        )
        self.assertEqual(
            expenses_in_range(self.tenant, self.today, self.today, hotel=self.prop_b),
            Decimal("900000"),
        )
        report_a = build_pnl_report(
            self.tenant, self.today.year, self.today.month, basis="cash", hotel=self.prop_a
        )
        self.assertEqual(report_a["expenses_total"], Decimal("100000"))

    def test_stock_list_and_expense_list_filter_active_branch(self):
        self._activate(self.prop_a)
        stock = self.client.get(reverse("inventory:list"))
        self.assertContains(stock, "Cola A")
        self.assertNotContains(stock, "Cola B")
        expenses = self.client.get(reverse("finance:list"))
        self.assertContains(expenses, "Gaz A")
        self.assertNotContains(expenses, "Gaz B")

    def test_cannot_approve_other_branch_expense(self):
        draft_b = Expense.objects.create(
            tenant=self.tenant,
            hotel=self.prop_b,
            category=self.cat,
            title="Draft B",
            amount=Decimal("1000"),
            expense_date=self.today,
            status=Expense.Status.DRAFT,
        )
        self._activate(self.prop_a)
        resp = self.client.post(reverse("finance:approve", args=[draft_b.pk]))
        self.assertEqual(resp.status_code, 302)
        draft_b.refresh_from_db()
        self.assertEqual(draft_b.status, Expense.Status.DRAFT)

    def test_cannot_view_other_branch_cash_shift_detail(self):
        shift_b = open_cash_shift(self.tenant, self.user, Decimal("500"), hotel=self.prop_b)
        self._activate(self.prop_a)
        resp = self.client.get(reverse("folio:cash_shift_detail", args=[shift_b.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_minibar_blocks_cross_branch_item(self):
        guest = Guest.objects.create(tenant=self.tenant, first_name="Iso")
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop_a,
            guest=guest,
            room_type=self.rt_a,
            room=self.room_a,
            rate_plan=self.rate_a,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
        )
        check_in_reservation(reservation, self.user)
        with self.assertRaises(ValidationError):
            sell_minibar(reservation=reservation, item=self.item_b, user=self.user)
