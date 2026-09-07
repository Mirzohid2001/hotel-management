from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.tests.helpers import setup_tenant_user
from hr.models import Employee, PayrollPeriod, SalaryAdvance, SalaryPayment
from hr.services import (
    create_advance,
    generate_payroll,
    mark_item_paid,
    pay_employee_salary,
    settle_advance,
)
from properties.models import Property, PropertySettings
from subscriptions.models import Plan


class SalaryAdvancePayrollTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="hradv")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        self.emp = Employee.objects.create(
            tenant=self.tenant,
            full_name="Ali Valiyev",
            base_salary=Decimal("5000000"),
        )
        today = timezone.localdate()
        self.year, self.month = today.year, today.month

    def test_advance_applies_on_generate_and_settle_on_finalize(self):
        create_advance(
            self.tenant,
            self.emp,
            amount=Decimal("500000"),
            advance_date=timezone.localdate(),
            note="Mid-month",
        )
        period = generate_payroll(self.tenant, self.year, self.month)
        item = period.items.get(employee=self.emp)
        self.assertEqual(item.advance, Decimal("500000"))
        self.assertEqual(item.net_amount, Decimal("4500000"))
        adv = SalaryAdvance.objects.get(employee=self.emp)
        self.assertEqual(adv.applied_to_period_id, period.pk)
        self.assertFalse(adv.is_settled)

        # To‘lash qoralamadan ham ishlaydi: avtomatik yakunlaydi
        mark_item_paid(item)
        adv.refresh_from_db()
        self.assertTrue(adv.is_settled)
        period.refresh_from_db()
        self.assertEqual(period.status, PayrollPeriod.Status.PAID)
        self.assertTrue(SalaryPayment.objects.filter(item=item).exists())

    def test_one_click_employee_pay(self):
        create_advance(
            self.tenant, self.emp, amount=Decimal("1000000"), note="Avans"
        )
        payment = pay_employee_salary(self.tenant, self.emp)
        self.assertEqual(payment.amount, Decimal("4000000"))
        self.assertTrue(
            SalaryAdvance.objects.get(employee=self.emp).is_settled
        )

        resp = self.client.post(reverse("hr:employee_pay", args=[self.emp.pk]))
        self.assertEqual(resp.status_code, 302)
        # ikkinchi marta — xato xabar, lekin redirect
        self.assertEqual(SalaryPayment.objects.filter(item__employee=self.emp).count(), 1)

    def test_payroll_bonus_deduction_edit(self):
        from hr.services import generate_payroll, update_payroll_item_amounts

        period = generate_payroll(self.tenant, self.year, self.month)
        item = period.items.get(employee=self.emp)
        update_payroll_item_amounts(
            item, bonus=Decimal("200000"), deduction=Decimal("50000")
        )
        item.refresh_from_db()
        self.assertEqual(item.bonus, Decimal("200000"))
        self.assertEqual(item.deduction, Decimal("50000"))
        self.assertEqual(item.net_amount, Decimal("5150000"))

        resp = self.client.post(
            reverse("hr:payroll_item_edit", args=[item.pk]),
            {"bonus": "100000", "deduction": "0"},
        )
        self.assertEqual(resp.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.bonus, Decimal("100000"))
        self.assertEqual(item.net_amount, Decimal("5100000"))

    def test_employee_advance_from_list(self):
        resp = self.client.post(
            reverse("hr:employee_advance", args=[self.emp.pk]),
            {
                "amount": "250000",
                "advance_date": timezone.localdate().isoformat(),
                "note": "Tez",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            SalaryAdvance.objects.filter(employee=self.emp, amount=Decimal("250000")).exists()
        )

    def test_manual_settle_and_ui(self):
        adv = create_advance(
            self.tenant, self.emp, amount=Decimal("100000"), note="Cash"
        )
        settle_advance(adv)
        adv.refresh_from_db()
        self.assertTrue(adv.is_settled)

        resp = self.client.get(reverse("hr:advances"))
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(
            reverse("hr:advance_create"),
            {
                "employee": self.emp.pk,
                "amount": "250000",
                "advance_date": timezone.localdate().isoformat(),
                "note": "UI",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            SalaryAdvance.objects.filter(employee=self.emp, amount=Decimal("250000")).exists()
        )

    def test_new_property_settings_require_id_default(self):
        prop = Property.objects.create(tenant=self.tenant, name="Docs Default Hotel")
        settings = PropertySettings.objects.create(tenant=self.tenant, property=prop)
        self.assertTrue(settings.require_id_on_checkin)
