from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.services import check_in_reservation, create_reservation
from core.tests.helpers import setup_tenant_user
from finance.models import Expense, ExpenseCategory
from folio.models import FolioCharge
from folio.services import add_charge, ensure_folio_for_reservation
from guests.models import Guest
from properties.models import Property, PropertySettings, RatePlan, Room, RoomType
from reports.accounting import (
    build_daily_flash,
    build_pnl_report,
    guest_ar_summary,
    payment_method_breakdown,
    revenue_by_charge_type,
)
from subscriptions.models import Plan


class AccountingReportsTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="acct")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        self.prop = Property.objects.create(tenant=self.tenant, name="Acct Hotel")
        PropertySettings.objects.create(
            tenant=self.tenant,
            property=self.prop,
            require_id_on_checkin=False,
            emehmon_fee=Decimal("0"),
        )
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Std",
            code="std",
            base_price=Decimal("100000"),
        )
        self.room = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="501"
        )
        self.rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="BAR",
            code="bar",
            price=Decimal("100000"),
        )
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Acct")
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
        folio = ensure_folio_for_reservation(self.reservation)
        add_charge(
            folio,
            self.user,
            charge_type=FolioCharge.ChargeType.SERVICE,
            description="Breakfast",
            unit_price=Decimal("50000"),
        )
        self.cat = ExpenseCategory.objects.create(tenant=self.tenant, name="Utilities")
        Expense.objects.create(
            tenant=self.tenant,
            hotel=self.prop,
            category=self.cat,
            title="Power",
            amount=Decimal("200000"),
            expense_date=self.today,
            status=Expense.Status.PAID,
        )

    def test_accrual_pnl_breakdown(self):
        report = build_pnl_report(
            self.tenant, self.today.year, self.today.month, basis="accrual"
        )
        self.assertGreater(report["revenue_total"], Decimal("0"))
        self.assertEqual(report["expenses_total"], Decimal("200000"))
        keys = {r["key"] for r in report["revenue_breakdown"]}
        self.assertIn("service", keys)

    def test_cash_pnl_includes_advance_commission_inventory(self):
        from bookings.models import BookingReferrer
        from hr.models import Employee, SalaryAdvance, SalaryPayment, PayrollItem, PayrollPeriod
        from inventory.models import StockItem, StockMovement
        from inventory.services import adjust_stock
        from reports.accounting import build_pnl_report, cash_pnl_for_range

        emp = Employee.objects.create(
            tenant=self.tenant, full_name="Cashier", base_salary=Decimal("3000000")
        )
        SalaryAdvance.objects.create(
            tenant=self.tenant,
            employee=emp,
            amount=Decimal("500000"),
            advance_date=self.today,
        )
        period = PayrollPeriod.objects.create(
            tenant=self.tenant,
            year=self.today.year,
            month=self.today.month,
            status=PayrollPeriod.Status.FINALIZED,
        )
        item = PayrollItem.objects.create(
            tenant=self.tenant,
            period=period,
            employee=emp,
            base_amount=Decimal("3000000"),
            advance=Decimal("500000"),
        )
        SalaryPayment.objects.create(
            tenant=self.tenant,
            item=item,
            amount=item.net_amount,
            paid_at=timezone.now(),
            method="cash",
        )

        referrer = BookingReferrer.objects.create(
            tenant=self.tenant,
            name="Agent",
            default_commission_percent=Decimal("10"),
        )
        self.reservation.referrer = referrer
        self.reservation.commission_percent = Decimal("10")
        self.reservation.check_out = self.today
        self.reservation.status = self.reservation.Status.CHECKED_OUT
        self.reservation.save(
            update_fields=[
                "referrer",
                "commission_percent",
                "check_out",
                "status",
                "updated_at",
            ]
        )

        stock = StockItem.objects.create(
            tenant=self.tenant,
            hotel=self.prop,
            name="Cola",
            sku="cola",
            unit_cost=Decimal("5000"),
            quantity_on_hand=Decimal("10"),
            is_minibar=True,
        )
        adjust_stock(
            stock,
            movement_type=StockMovement.MovementType.OUT,
            quantity=Decimal("10"),
            user=self.user,
        )

        report = build_pnl_report(
            self.tenant, self.today.year, self.today.month, basis="cash"
        )
        self.assertEqual(report["advances"], Decimal("500000"))
        # Yalpi mehnat = baza (avans ushlansa ham)
        self.assertEqual(report["payroll"], Decimal("3000000"))
        self.assertEqual(report["inventory_cost"], Decimal("50000"))
        self.assertGreater(report["commission"], Decimal("0"))
        # Avans sof foydadan ayirilmaydi (xodim qarzi)
        expected_ops = (
            report["expenses_total"]
            + report["payroll"]
            + report["commission"]
            + report["inventory_cost"]
            + report.get("emehmon_shortfall", Decimal("0"))
        )
        self.assertEqual(report["operating_costs"], expected_ops)
        self.assertEqual(report["labor_total"], report["payroll"])
        self.assertEqual(report["net"], report["revenue_total"] - expected_ops)

        ranged = cash_pnl_for_range(self.tenant, self.today, self.today)
        self.assertEqual(ranged["operating_costs"], expected_ops)

    def test_emehmon_pass_through_pnl(self):
        """E-mehmon tushum emas; faqat qoplanmagan farq rasxod."""
        from folio.services import collect_emehmon_fee, add_payment
        from folio.models import GuestPayment
        from reports.accounting import build_pnl_report, cash_pnl_for_range

        settings = self.prop.settings
        settings.emehmon_fee = Decimal("9000")
        settings.save(update_fields=["emehmon_fee"])

        # 2 o‘tgan kecha × 1 mehmon = 18000 expected; half collected → shortfall 9000
        self.reservation.emehmon_required = True
        self.reservation.check_in = self.today - timedelta(days=1)
        self.reservation.check_out = self.today + timedelta(days=1)
        self.reservation.adults = 1
        self.reservation.save(
            update_fields=["emehmon_required", "check_in", "check_out", "adults", "updated_at"]
        )

        collect_emehmon_fee(
            self.reservation,
            self.user,
            amount=Decimal("9000"),
            method=GuestPayment.Method.CARD,
        )
        # Extra room payment should stay in revenue
        from folio.services import ensure_folio_for_reservation

        folio = ensure_folio_for_reservation(self.reservation)
        add_payment(
            folio,
            self.user,
            amount=Decimal("100000"),
            method=GuestPayment.Method.CARD,
            note="Xona",
        )

        report = build_pnl_report(
            self.tenant, self.today.year, self.today.month, basis="cash"
        )
        # 9000 E-mehmon payment excluded from revenue; 100000 remains
        self.assertEqual(report["revenue_total"], Decimal("100000"))
        self.assertEqual(report["emehmon_shortfall"], Decimal("9000"))
        labels = " ".join(str(r["label"]) for r in report["expenses_breakdown"])
        self.assertIn("E-mehmon", labels)

        # Accrual: EMEHMON charge not in revenue
        from folio.models import FolioCharge
        from reports.accounting import revenue_by_charge_type

        rev = revenue_by_charge_type(self.tenant, self.today.year, self.today.month)
        keys = {r["key"] for r in rev["breakdown"]}
        self.assertNotIn(FolioCharge.ChargeType.EMEHMON, keys)

        ranged = cash_pnl_for_range(self.tenant, self.today, self.today)
        self.assertEqual(ranged["guest_payments"], Decimal("100000"))
        from calendar import monthrange

        month_start = self.today.replace(day=1)
        month_end = self.today.replace(
            day=monthrange(self.today.year, self.today.month)[1]
        )
        month_pnl = cash_pnl_for_range(self.tenant, month_start, month_end)
        self.assertEqual(month_pnl["emehmon_shortfall"], Decimal("9000"))
        self.assertEqual(month_pnl["guest_payments"], Decimal("100000"))

    def test_reinvestment_excluded_from_pnl_net(self):
        """Reinvestitsiya Sof/P&Ldan ayirilmaydi — faqat foyda ulushida."""
        from maintenance.services import record_maintenance_spend
        from reports.accounting import build_pnl_report, cash_pnl_for_range

        before = build_pnl_report(
            self.tenant, self.today.year, self.today.month, basis="cash"
        )
        record_maintenance_spend(
            self.tenant,
            self.user,
            hotel=self.prop,
            title="Katta remont",
            amount=Decimal("5000000"),
            expense_date=self.today,
            funding=Expense.Funding.REINVESTMENT,
        )
        after = build_pnl_report(
            self.tenant, self.today.year, self.today.month, basis="cash"
        )
        self.assertEqual(after["expenses_total"], before["expenses_total"])
        self.assertEqual(after["net"], before["net"])
        self.assertEqual(after["reinvestment"], Decimal("5000000"))
        self.assertEqual(after["operating_costs"], before["operating_costs"])

        ranged = cash_pnl_for_range(self.tenant, self.today, self.today)
        self.assertEqual(ranged["reinvestment"], Decimal("5000000"))
        self.assertEqual(ranged["net"], after["net"])

    def test_flash_cash_includes_company_payments(self):
        from folio.models import CompanyInvoice, CompanyInvoiceLine, CompanyPayment
        from guests.models import Company
        from reports.accounting import build_daily_flash
        from reports.services import revenue_on

        company = Company.objects.create(tenant=self.tenant, name="Corp")
        inv = CompanyInvoice.objects.create(
            tenant=self.tenant,
            hotel=self.prop,
            company=company,
            code="INV-TEST-0001",
            created_by=self.user,
        )
        CompanyInvoiceLine.objects.create(
            tenant=self.tenant,
            invoice=inv,
            description="Stay",
            amount=Decimal("250000"),
        )
        CompanyPayment.objects.create(
            tenant=self.tenant,
            invoice=inv,
            amount=Decimal("250000"),
            method="card",
            received_by=self.user,
        )
        self.assertEqual(
            revenue_on(self.tenant, self.today, hotel=self.prop),
            Decimal("250000"),
        )
        flash = build_daily_flash(self.tenant, self.today, hotel=self.prop)
        self.assertEqual(flash["revenue_cash"], Decimal("250000"))

    def test_emehmon_shortfall_does_not_count_future_nights(self):
        """Joriy oy Sofi kelajak kechalarini oldindan ayirmasin."""
        from bookings.emehmon import emehmon_shortfall_for_range, nights_overlap
        from calendar import monthrange

        settings = self.prop.settings
        settings.emehmon_fee = Decimal("9000")
        settings.save(update_fields=["emehmon_fee"])
        self.reservation.emehmon_required = True
        self.reservation.adults = 1
        self.reservation.check_out = self.today + timedelta(days=10)
        self.reservation.save(
            update_fields=["emehmon_required", "adults", "check_out", "updated_at"]
        )
        # already checked in in setUp

        month_start = self.today.replace(day=1)
        month_end = self.today.replace(
            day=monthrange(self.today.year, self.today.month)[1]
        )
        shortfall = emehmon_shortfall_for_range(
            self.tenant, month_start, month_end, hotel=self.prop
        )
        expected_nights = nights_overlap(
            self.reservation.check_in,
            self.reservation.check_out,
            month_start,
            self.today,
        )
        self.assertEqual(shortfall, Decimal(expected_nights) * Decimal("9000"))
        full_month_nights = nights_overlap(
            self.reservation.check_in,
            self.reservation.check_out,
            month_start,
            month_end,
        )
        if full_month_nights > expected_nights:
            self.assertLess(shortfall, Decimal(full_month_nights) * Decimal("9000"))

    def test_flash_and_guest_ar(self):
        flash = build_daily_flash(self.tenant, self.today)
        self.assertEqual(flash["day"], self.today)
        ar = guest_ar_summary(self.tenant)
        self.assertGreaterEqual(ar["total"], Decimal("0"))

    def test_pnl_and_flash_pages(self):
        resp = self.client.get(reverse("reports:pnl"))
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(reverse("reports:flash"))
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(
            reverse("reports:flash_print"), {"day": self.today.isoformat()}
        )
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(reverse("reports:history"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Hisobotlar tarixi")
        resp = self.client.get(
            reverse("reports:pnl_print"),
            {"year": self.today.year, "month": self.today.month},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "chek")
        self.assertContains(resp, "Kunlik hisobot")
        self.assertContains(resp, "Chop etish")
        resp = self.client.get(reverse("reports:export_ar"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp["Content-Type"])

    def test_revenue_by_charge_type(self):
        rev = revenue_by_charge_type(self.tenant, self.today.year, self.today.month)
        self.assertGreater(rev["total"], Decimal("0"))

    def test_payment_methods_refunds_are_out_not_in(self):
        from folio.models import GuestPayment

        GuestPayment.objects.create(
            tenant=self.tenant,
            folio=self.reservation.folio,
            amount=Decimal("150000"),
            method=GuestPayment.Method.CASH,
            kind=GuestPayment.Kind.PAYMENT,
            received_by=self.user,
            currency="UZS",
        )
        GuestPayment.objects.create(
            tenant=self.tenant,
            folio=self.reservation.folio,
            amount=Decimal("50000"),
            method=GuestPayment.Method.CASH,
            kind=GuestPayment.Kind.REFUND,
            received_by=self.user,
            currency="UZS",
            note="Sdachi test",
        )
        breakdown = payment_method_breakdown(self.tenant, self.today, self.today)
        cash = next(r for r in breakdown["rows"] if r["method"] == "cash")
        self.assertEqual(cash["in"], Decimal("150000"))
        # Sdachi 50k + setUp rasxod 200k (cash)
        self.assertEqual(cash["out"], Decimal("250000"))

    def test_flash_separates_reinvestment_from_operating_out(self):
        """Reinvest kassadan chiqadi, lekin Rasxod (joriy) / Sofga kirmaydi."""
        from maintenance.services import record_maintenance_spend
        from reports.accounting import build_daily_flash, payment_method_breakdown

        record_maintenance_spend(
            self.tenant,
            self.user,
            hotel=self.prop,
            title="Katta remont",
            amount=Decimal("5000000"),
            expense_date=self.today,
            funding=Expense.Funding.REINVESTMENT,
            payment_method=Expense.PaymentMethod.CASH,
        )
        flash = build_daily_flash(self.tenant, self.today, hotel=self.prop)
        self.assertEqual(flash["expenses_today"], Decimal("200000"))  # setUp Power
        self.assertEqual(flash["reinvestment_today"], Decimal("5000000"))
        self.assertEqual(flash["payments"]["reinvestment_out"], Decimal("5000000"))
        self.assertGreaterEqual(flash["payments"]["operating_out"], Decimal("200000"))
        cash = next(
            r for r in flash["payments"]["rows"] if r["method"] == Expense.PaymentMethod.CASH
        )
        self.assertEqual(cash["reinvest_out"], Decimal("5000000"))
        # Sof o‘zgarmagan (reinvest ayirilmagan)
        from reports.accounting import cash_pnl_for_range

        pnl = cash_pnl_for_range(self.tenant, self.today, self.today, hotel=self.prop)
        self.assertEqual(pnl["reinvestment"], Decimal("5000000"))
        self.assertEqual(pnl["expenses_total"], Decimal("200000"))
