from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from core.tests.helpers import setup_tenant_user
from properties.models import Property, Room, RoomType
from reports.chart_data import dashboard_charts, flash_charts, occupancy_trend, pnl_charts, cash_shift_charts
from subscriptions.models import Plan


class ChartDataTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="charts")
        self.tenant = self.ctx["tenant"]
        self.prop = Property.objects.create(tenant=self.tenant, name="Chart Hotel")
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Std",
            code="std",
            base_price=Decimal("100000"),
        )
        Room.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            number="101",
            status=Room.Status.READY,
        )
        self.today = timezone.localdate()

    def test_occupancy_trend_seven_days(self):
        rows = occupancy_trend(self.tenant, self.today, hotel=self.prop)
        self.assertEqual(len(rows), 7)
        self.assertTrue(rows[-1]["is_today"])

    def test_dashboard_charts_structure(self):
        data = dashboard_charts(self.tenant, self.today, hotel=self.prop, currency="UZS")
        self.assertEqual(len(data["revenueTrend"]["labels"]), 7)
        self.assertEqual(len(data["revenueTrend"]["occupancy"]), 7)
        self.assertIn("roomStatus", data)

    def test_pnl_charts_structure(self):
        report = {
            "revenue_breakdown": [{"label": "Xona", "amount": Decimal("100000")}],
            "expenses_breakdown": [{"label": "Kommunal", "amount": Decimal("20000")}],
            "revenue_total": Decimal("100000"),
            "expenses_total": Decimal("20000"),
            "payroll": Decimal("30000"),
            "advances": Decimal("5000"),
            "commission": Decimal("2000"),
            "inventory_cost": Decimal("1000"),
            "emehmon_shortfall": Decimal("0"),
            "net": Decimal("42000"),
        }
        data = pnl_charts(report, currency="UZS")
        self.assertEqual(len(data["revenueDonut"]["values"]), 1)
        self.assertEqual(len(data["summaryBar"]["values"]), 7)

    def test_flash_charts_structure(self):
        flash = {
            "payments": {"rows": [{"label": "Naqd", "in": Decimal("100"), "out": Decimal("0")}]},
            "guest_ar": {"rows": [{"code": "R-1", "balance": Decimal("50000")}]},
            "revenue_cash": Decimal("100"),
            "revenue_accrual": Decimal("150"),
            "expenses_today": Decimal("20"),
            "mtd": {
                "revenue": Decimal("1000"),
                "expenses": Decimal("200"),
                "payroll": Decimal("300"),
                "operating_costs": Decimal("550"),
                "net": Decimal("450"),
            },
        }
        data = flash_charts(flash, currency="UZS")
        self.assertEqual(len(data["paymentMethods"]["labels"]), 1)
        self.assertEqual(len(data["mtdBar"]["values"]), 3)

    def test_cash_shift_charts_structure(self):
        from folio.models import CashShift

        shift = CashShift(opening_float=Decimal("100000"))
        report = {
            "shift": shift,
            "payments": {"cash_in": Decimal("50000"), "card_total": Decimal("30000"), "transfer_total": Decimal("10000")},
            "cash_out": {"total": Decimal("20000")},
            "expected_cash": Decimal("130000"),
        }
        history = [{"label": "01.09", "variance": Decimal("-500")}]
        data = cash_shift_charts(report, history, currency="UZS")
        self.assertIn("paymentMix", data)
        self.assertIn("varianceHistory", data)
