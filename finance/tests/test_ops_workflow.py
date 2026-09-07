from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.tests.helpers import setup_tenant_user
from finance.models import Expense, ExpenseCategory
from finance.services import approve_expense, mark_expense_paid, reject_expense
from guests.models import Guest
from housekeeping.models import HousekeepingTask
from housekeeping.services import assign_task, set_room_status
from properties.models import Property, Room, RoomType
from subscriptions.models import Plan
from tenants.models import TenantMembership


class ExpenseHkBlacklistUiTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="ops5")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        self.cat = ExpenseCategory.objects.create(tenant=self.tenant, name="Ops")
        self.prop = Property.objects.create(tenant=self.tenant, name="Ops5 Hotel")
        self.rt = RoomType.objects.create(
            tenant=self.tenant, property=self.prop, name="S", code="s", base_price=Decimal("1")
        )
        self.room = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="11"
        )

    def test_expense_approve_reject_pay(self):
        expense = Expense.objects.create(
            tenant=self.tenant,
            hotel=self.prop,
            category=self.cat,
            title="Water",
            amount=Decimal("10000"),
            expense_date=timezone.localdate(),
        )
        approve_expense(expense, self.user)
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.APPROVED)
        mark_expense_paid(expense, self.user)
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.PAID)
        self.assertIsNotNone(expense.paid_at)

        draft = Expense.objects.create(
            tenant=self.tenant,
            hotel=self.prop,
            category=self.cat,
            title="Bad",
            amount=Decimal("1"),
            expense_date=timezone.localdate(),
        )
        reject_expense(draft, self.user, reason="Duplicate")
        draft.refresh_from_db()
        self.assertEqual(draft.status, Expense.Status.REJECTED)
        self.assertEqual(draft.rejection_reason, "Duplicate")
        with self.assertRaises(ValidationError):
            approve_expense(draft, self.user)

    def test_hk_assign_task(self):
        set_room_status(self.room, "dirty", user=self.user)
        task = HousekeepingTask.objects.create(
            tenant=self.tenant, room=self.room, title="Cleaning"
        )
        assign_task(task, self.user)
        task.refresh_from_db()
        self.assertEqual(task.assigned_to_id, self.user.pk)
        self.assertEqual(task.status, HousekeepingTask.Status.IN_PROGRESS)
        resp = self.client.get(reverse("housekeeping:board"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Biriktirish")

    def test_blacklist_badge_on_guest_list(self):
        Guest.objects.create(
            tenant=self.tenant,
            first_name="Blocked",
            is_blacklisted=True,
            blacklist_reason="Debt",
        )
        resp = self.client.get(reverse("guests:list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "badge-blacklist")
        self.assertContains(resp, "Qora ro‘yxat")
