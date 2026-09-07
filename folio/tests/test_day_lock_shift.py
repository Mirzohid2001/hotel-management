from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from bookings.services import check_in_reservation, create_reservation
from core.models import ActivityLog
from core.tests.helpers import make_membership, make_user, setup_tenant_user
from finance.models import Expense, ExpenseCategory
from finance.services import mark_expense_paid
from folio.services import (
    add_payment,
    close_cash_shift,
    get_open_shift,
    open_cash_shift,
)
from folio.shift_report import build_shift_report
from guests.models import Guest
from properties.models import Property, PropertySettings, RatePlan, Room, RoomType
from reports.day_lock import assert_day_open, is_day_locked
from reports.night_audit import run_night_audit
from subscriptions.models import Plan
from tenants.models import TenantMembership


class DayLockAndShiftTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="lockshift")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.prop = Property.objects.create(tenant=self.tenant, name="Lock Hotel")
        PropertySettings.objects.create(
            tenant=self.tenant, property=self.prop, require_id_on_checkin=False
        )
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Std",
            code="std",
            base_price=Decimal("100000"),
        )
        self.room = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="901"
        )
        self.rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="BAR",
            code="bar",
            price=Decimal("100000"),
        )
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Lock")
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
            check_out=self.today + timedelta(days=1),
        )
        check_in_reservation(self.reservation, self.user)
        open_cash_shift(self.tenant, self.user, Decimal("0"), hotel=self.prop)

    def test_day_lock_blocks_payment(self):
        run_night_audit(self.tenant, self.user, audit_date=self.today, hotel=self.prop)
        self.assertTrue(is_day_locked(self.tenant, self.today))
        clerk = make_user(username=f"clerk_{self._testMethodName}")
        make_membership(clerk, self.tenant, role=TenantMembership.Role.MANAGER)
        folio = self.reservation.folio
        with self.assertRaises(ValidationError):
            add_payment(folio, clerk, amount=Decimal("1000"))
        assert_day_open(self.tenant, self.today, self.user)

    def test_shift_report_with_cash_out(self):
        cat = ExpenseCategory.objects.create(tenant=self.tenant, name="Ops")
        expense = Expense.objects.create(
            tenant=self.tenant,
            hotel=self.prop,
            category=cat,
            title="Supplies",
            amount=Decimal("30000"),
            expense_date=self.today,
            status=Expense.Status.APPROVED,
            payment_method=Expense.PaymentMethod.CASH,
        )
        mark_expense_paid(expense, self.user)
        add_payment(self.reservation.folio, self.user, amount=Decimal("50000"))
        shift = get_open_shift(self.tenant, hotel=self.prop)
        report = build_shift_report(shift)
        self.assertEqual(report["cash_out"]["expenses"], Decimal("30000"))
        self.assertEqual(report["payments"]["cash_in"], Decimal("50000"))
        self.assertEqual(report["expected_cash"], Decimal("20000"))
        closed = close_cash_shift(shift, self.user, Decimal("20000"))
        self.assertEqual(closed.variance, Decimal("0"))
        self.assertGreater(ActivityLog.objects.filter(action="cash_shift_closed").count(), 0)

    def test_payroll_uses_datetime_in_shift_window(self):
        from hr.models import Employee, PayrollPeriod, PayrollItem, SalaryPayment
        from hr.services import finalize_payroll, generate_payroll, mark_item_paid

        emp = Employee.objects.create(
            tenant=self.tenant, full_name="Cashier Pay", base_salary=Decimal("1000000")
        )
        period = generate_payroll(self.tenant, self.today.year, self.today.month)
        finalize_payroll(period)
        item = period.items.get(employee=emp)
        payment = mark_item_paid(item, amount=Decimal("10000"), method="cash")
        self.assertIsNotNone(payment.paid_at.hour)  # datetime, not bare date
        shift = get_open_shift(self.tenant, hotel=self.prop)
        report = build_shift_report(shift)
        self.assertEqual(report["cash_out"]["payroll"], Decimal("10000"))

        # Payment before shift opened must not count
        SalaryPayment.objects.filter(pk=payment.pk).update(
            paid_at=shift.opened_at - timedelta(hours=2)
        )
        report2 = build_shift_report(shift)
        self.assertEqual(report2["cash_out"]["payroll"], Decimal("0"))
