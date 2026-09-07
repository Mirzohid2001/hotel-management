"""Phase 3 — rasxodlar HTMX bir bosish tasdiqlash/to‘lov."""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.tests.helpers import make_property_stack, setup_tenant_user
from finance.models import Expense, ExpenseCategory, Vendor
from subscriptions.models import Plan


class ExpenseHtmxTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="exhtmx")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        stack = make_property_stack(self.tenant, room_number="EH1")
        self.prop = stack["property"]
        self.cat = ExpenseCategory.objects.create(tenant=self.tenant, name="Ops")
        self.vendor = Vendor.objects.create(tenant=self.tenant, name="Supplier")

    def _draft(self, title="Draft expense"):
        return Expense.objects.create(
            tenant=self.tenant,
            hotel=self.prop,
            category=self.cat,
            vendor=self.vendor,
            title=title,
            amount=Decimal("50000"),
            expense_date=timezone.localdate(),
        )

    def test_list_shows_htmx_approve_form(self):
        expense = self._draft()
        resp = self.client.get(reverse("finance:list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f'id="expense-row-{expense.pk}"')
        self.assertContains(resp, reverse("finance:approve", args=[expense.pk]))

    def test_approve_htmx_returns_updated_row(self):
        expense = self._draft()
        url = reverse("finance:approve", args=[expense.pk])
        resp = self.client.post(url, HTTP_HX_REQUEST="true")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f'id="expense-row-{expense.pk}"')
        self.assertContains(resp, "Tasdiqlangan")
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.APPROVED)

    def test_pay_htmx_returns_paid_row(self):
        expense = self._draft("Pay me")
        self.client.post(reverse("finance:approve", args=[expense.pk]))
        url = reverse("finance:pay", args=[expense.pk])
        resp = self.client.post(url, HTTP_HX_REQUEST="true")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "To‘langan")
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.PAID)

    def test_reject_htmx_returns_rejected_row(self):
        expense = self._draft("Reject me")
        url = reverse("finance:reject", args=[expense.pk])
        resp = self.client.post(
            url,
            {"reason": "Not needed"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Rad etilgan")
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.REJECTED)
