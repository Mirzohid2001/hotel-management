from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from core.tests.helpers import make_property_stack, setup_tenant_user
from finance.models import Expense, ExpenseCategory
from hr.models import Employee
from hr.services import finalize_payroll, generate_payroll, mark_item_paid
from subscriptions.models import Plan


class FinanceHRTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="finhr")
        stack = make_property_stack(self.ctx["tenant"], room_number="FH1")
        self.prop = stack["property"]

    def test_expense_and_payroll(self):
        cat = ExpenseCategory.objects.create(tenant=self.ctx["tenant"], name="Utilities")
        expense = Expense.objects.create(
            tenant=self.ctx["tenant"],
            hotel=self.prop,
            category=cat,
            title="Electricity",
            amount=Decimal("500000"),
            expense_date=timezone.localdate(),
        )
        self.assertEqual(expense.status, Expense.Status.DRAFT)
        emp = Employee.objects.create(
            tenant=self.ctx["tenant"],
            full_name="Worker",
            base_salary=Decimal("2000000"),
        )
        today = timezone.localdate()
        period = generate_payroll(self.ctx["tenant"], today.year, today.month)
        item = period.items.get(employee=emp)
        self.assertEqual(item.net_amount, Decimal("2000000"))
        finalize_payroll(period)
        payment = mark_item_paid(item)
        self.assertEqual(payment.amount, Decimal("2000000"))
