from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.tests.helpers import setup_tenant_user
from hr.models import Employee, PayrollItem, PayrollPeriod, SalaryAdvance, SalaryPayment
from hr.services import (
    create_advance,
    generate_payroll,
    pay_all_unpaid,
    pay_employee_daily,
    pay_employee_salary,
)
from reports.accounting import cash_pnl_for_range, payment_method_breakdown
from subscriptions.models import Plan


class DailyWageAccountingTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="hrdaily")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        self.today = timezone.localdate()
        self.daily = Employee.objects.create(
            tenant=self.tenant,
            full_name="Kunlik Ishchi",
            salary_type=Employee.SalaryType.DAILY,
            base_salary=Decimal("100000"),
        )
        self.monthly = Employee.objects.create(
            tenant=self.tenant,
            full_name="Oylik Xodim",
            salary_type=Employee.SalaryType.MONTHLY,
            base_salary=Decimal("3000000"),
        )

    def test_generate_payroll_skips_daily_employees(self):
        period = generate_payroll(self.tenant, self.today.year, self.today.month)
        self.assertTrue(period.items.filter(employee=self.monthly).exists())
        self.assertFalse(period.items.filter(employee=self.daily).exists())

    def test_daily_pay_gross_in_sof_net_in_cash(self):
        create_advance(
            self.tenant, self.daily, amount=Decimal("50000"), note="Avans"
        )
        payment = pay_employee_daily(self.tenant, self.daily, days=3)
        # 3 × 100000 − 50000 avans = 250000 sof kassa
        self.assertEqual(payment.amount, Decimal("250000"))
        item = payment.item
        self.assertEqual(item.days_count, 3)
        self.assertEqual(item.base_amount, Decimal("300000"))
        self.assertEqual(item.advance, Decimal("50000"))
        self.assertEqual(item.work_date, self.today)

        pnl = cash_pnl_for_range(self.tenant, self.today, self.today)
        # Sof: yalpi 300000 (avans Sofdan ayrilmaydi)
        self.assertEqual(pnl["payroll"], Decimal("300000"))
        self.assertEqual(pnl["advances"], Decimal("50000"))
        self.assertEqual(pnl["labor_total"], Decimal("300000"))

        breakdown = payment_method_breakdown(self.tenant, self.today, self.today)
        cash = next(r for r in breakdown["rows"] if r["method"] == "cash")
        # Kassadan: sof to‘lov 250000 + avans chiqimi 50000
        self.assertGreaterEqual(cash["out"], Decimal("300000"))

    def test_daily_can_pay_multiple_days_in_month(self):
        pay_employee_daily(
            self.tenant, self.daily, days=1, work_date=self.today
        )
        other = self.today - timedelta(days=1)
        if other.month != self.today.month:
            other = self.today + timedelta(days=1)
        pay_employee_daily(self.tenant, self.daily, days=2, work_date=other)
        self.assertEqual(
            SalaryPayment.objects.filter(item__employee=self.daily).count(), 2
        )
        pnl = cash_pnl_for_range(
            self.tenant,
            min(self.today, other),
            max(self.today, other),
        )
        self.assertEqual(pnl["payroll"], Decimal("300000"))  # 1+2 days

    def test_same_work_date_cannot_pay_twice(self):
        pay_employee_daily(self.tenant, self.daily, days=1, work_date=self.today)
        with self.assertRaises(ValidationError):
            pay_employee_daily(
                self.tenant, self.daily, days=1, work_date=self.today
            )

    def test_pay_all_unpaid_skips_daily(self):
        generate_payroll(self.tenant, self.today.year, self.today.month)
        # Kunlikni qo‘lda yaratib qo‘ymaymiz — pay_all faqat oylik
        count = pay_all_unpaid(
            self.tenant, year=self.today.year, month=self.today.month
        )
        self.assertEqual(count, 1)
        self.assertTrue(
            SalaryPayment.objects.filter(item__employee=self.monthly).exists()
        )
        self.assertFalse(
            SalaryPayment.objects.filter(item__employee=self.daily).exists()
        )

    def test_monthly_pay_rejects_daily_employee(self):
        with self.assertRaises(ValidationError):
            pay_employee_salary(self.tenant, self.daily)

    def test_ui_daily_pay_form_and_list(self):
        resp = self.client.get(reverse("hr:employees"))
        self.assertContains(resp, "Kunlik")
        self.assertContains(resp, "Kunlik to‘lash")
        self.assertContains(resp, "Oylik to‘lash")

        resp = self.client.get(reverse("hr:employee_pay", args=[self.daily.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Kunlik to‘lash")

        resp = self.client.post(
            reverse("hr:employee_pay", args=[self.daily.pk]),
            {
                "days": "2",
                "work_date": self.today.isoformat(),
                "method": "cash",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            PayrollItem.objects.get(employee=self.daily).base_amount,
            Decimal("200000"),
        )
