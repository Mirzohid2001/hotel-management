"""Moslashuvchan rasxod boshqaruvi — edit, filter, reopen, setup."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.tests.helpers import make_property_stack, setup_tenant_user
from finance.models import Expense, ExpenseCategory, Vendor
from finance.services import delete_expense, reopen_expense
from subscriptions.models import Plan


class FlexibleExpenseTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="flexexp")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        stack = make_property_stack(self.tenant, room_number="FX1")
        self.prop = stack["property"]
        self.cat = ExpenseCategory.objects.create(tenant=self.tenant, name="Kommunal")
        self.vendor = Vendor.objects.create(tenant=self.tenant, name="UzGas")
        self.today = timezone.localdate()

    def _expense(self, **kwargs):
        data = {
            "tenant": self.tenant,
            "hotel": self.prop,
            "category": self.cat,
            "title": "Gaz",
            "amount": Decimal("50000"),
            "expense_date": self.today,
            "created_by": self.user,
        }
        data.update(kwargs)
        return Expense.objects.create(**data)

    def test_edit_draft_expense(self):
        expense = self._expense()
        url = reverse("finance:edit", args=[expense.pk])
        resp = self.client.post(
            url,
            {
                "category": self.cat.pk,
                "vendor": self.vendor.pk,
                "title": "Gaz yangilangan",
                "amount": "75000",
                "currency": "UZS",
                "expense_date": self.today.isoformat(),
                "payment_method": "transfer",
                "notes": "oylik",
            },
        )
        self.assertEqual(resp.status_code, 302)
        expense.refresh_from_db()
        self.assertEqual(expense.title, "Gaz yangilangan")
        self.assertEqual(expense.amount, Decimal("75000"))
        self.assertEqual(expense.vendor_id, self.vendor.pk)

    def test_cannot_edit_paid_expense(self):
        expense = self._expense(status=Expense.Status.PAID)
        resp = self.client.get(reverse("finance:edit", args=[expense.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("finance:list"))

    def test_filter_by_category_and_q(self):
        self._expense(title="Suv")
        other = ExpenseCategory.objects.create(tenant=self.tenant, name="Ofis")
        self._expense(title="Qog‘oz", category=other, amount=Decimal("1000"))
        resp = self.client.get(
            reverse("finance:list"),
            {"category": str(self.cat.pk), "q": "Suv"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Suv")
        self.assertNotContains(resp, "Qog‘oz")
        self.assertEqual(resp.context["filter_count"], 1)

    def test_reopen_rejected_then_delete(self):
        expense = self._expense(status=Expense.Status.REJECTED, rejection_reason="xato")
        reopen_expense(expense, self.user)
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.DRAFT)
        delete_expense(expense, self.user)
        self.assertFalse(Expense.objects.filter(pk=expense.pk).exists())

    def test_reopen_via_view(self):
        expense = self._expense(status=Expense.Status.REJECTED, rejection_reason="dup")
        resp = self.client.post(reverse("finance:reopen", args=[expense.pk]))
        self.assertEqual(resp.status_code, 302)
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.DRAFT)

    def test_cannot_delete_paid(self):
        expense = self._expense(status=Expense.Status.PAID)
        with self.assertRaises(ValidationError):
            delete_expense(expense, self.user)

    def test_category_edit_and_toggle(self):
        resp = self.client.post(
            reverse("finance:category_edit", args=[self.cat.pk]),
            {"name": "Kommunal yangi", "is_active": True},
        )
        self.assertEqual(resp.status_code, 302)
        self.cat.refresh_from_db()
        self.assertEqual(self.cat.name, "Kommunal yangi")
        self.client.post(reverse("finance:category_toggle", args=[self.cat.pk]))
        self.cat.refresh_from_db()
        self.assertFalse(self.cat.is_active)

    def test_vendor_edit(self):
        resp = self.client.post(
            reverse("finance:vendor_edit", args=[self.vendor.pk]),
            {"name": "UzGas Plus", "phone": "99890", "notes": "", "is_active": True},
        )
        self.assertEqual(resp.status_code, 302)
        self.vendor.refresh_from_db()
        self.assertEqual(self.vendor.name, "UzGas Plus")
        self.assertEqual(self.vendor.phone, "99890")
