from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.tests.helpers import setup_tenant_user
from finance.models import Expense, ExpenseCategory, ProfitPartner, ProfitPeriod
from finance.profit import (
    build_partner_ledger,
    ensure_open_period,
    record_withdrawal,
    reset_profit_period,
)
from folio.models import GuestPayment
from folio.services import ensure_folio_for_reservation
from bookings.services import check_in_reservation, create_reservation
from guests.models import Guest
from properties.models import Property, PropertySettings, RatePlan, Room, RoomType
from subscriptions.models import Plan


class ProfitShareTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="profit")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        self.prop = Property.objects.create(tenant=self.tenant, name="Share Hotel")
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
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="101"
        )
        self.rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="BAR",
            code="bar",
            price=Decimal("100000"),
        )
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="P")
        self.today = timezone.localdate()
        today = self.today
        res = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=today,
            check_out=today + timedelta(days=1),
        )
        check_in_reservation(res, self.user)
        folio = ensure_folio_for_reservation(res)
        GuestPayment.objects.create(
            tenant=self.tenant,
            folio=folio,
            amount=Decimal("1000000"),
            method=GuestPayment.Method.CARD,
            kind=GuestPayment.Kind.PAYMENT,
            received_by=self.user,
        )
        cat = ExpenseCategory.objects.create(tenant=self.tenant, name="Ops")
        Expense.objects.create(
            tenant=self.tenant,
            hotel=self.prop,
            category=cat,
            title="Power",
            amount=Decimal("200000"),
            expense_date=today,
            status=Expense.Status.PAID,
            created_by=self.user,
        )
        self.me = ProfitPartner.objects.create(
            tenant=self.tenant, name="Men", share_percent=Decimal("30")
        )
        self.anvar = ProfitPartner.objects.create(
            tenant=self.tenant, name="Anvar", share_percent=Decimal("40")
        )
        ProfitPartner.objects.create(
            tenant=self.tenant, name="Alisher", share_percent=Decimal("20")
        )
        ProfitPartner.objects.create(
            tenant=self.tenant, name="Sherali", share_percent=Decimal("10")
        )

    def test_ledger_splits_net_by_share(self):
        ledger = build_partner_ledger(self.tenant)
        # 1_000_000 - 200_000 = 800_000 net
        self.assertEqual(ledger["net"], Decimal("800000.00"))
        by_name = {r["partner"].name: r for r in ledger["rows"]}
        self.assertEqual(by_name["Men"]["entitled"], Decimal("240000.00"))
        self.assertEqual(by_name["Anvar"]["entitled"], Decimal("320000.00"))
        self.assertEqual(by_name["Alisher"]["entitled"], Decimal("160000.00"))
        self.assertEqual(by_name["Sherali"]["entitled"], Decimal("80000.00"))

    def test_partial_withdrawal_and_reset(self):
        record_withdrawal(
            self.tenant,
            self.user,
            partner=self.anvar,
            amount=Decimal("100000"),
        )
        ledger = build_partner_ledger(self.tenant)
        anvar = next(r for r in ledger["rows"] if r["partner"].pk == self.anvar.pk)
        self.assertEqual(anvar["withdrawn"], Decimal("100000.00"))
        self.assertEqual(anvar["remaining"], Decimal("220000.00"))

        closed, fresh = reset_profit_period(self.tenant, self.user)
        self.assertIsNotNone(closed.ended_on)
        self.assertTrue(fresh.is_open)
        self.assertEqual(fresh.started_on, closed.ended_on + timedelta(days=1))

        new_ledger = build_partner_ledger(self.tenant, period=fresh)
        # New period starts tomorrow — no revenue yet in fresh window if end < start handled
        # period_bounds uses today as end; if started_on is tomorrow, end may be today < start
        # Our reset sets start = end+1; if end=today, start=tomorrow, bounds clamp end to start
        self.assertEqual(new_ledger["withdrawn_total"], Decimal("0.00"))
        self.assertEqual(ProfitPeriod.objects.filter(tenant=self.tenant).count(), 2)

    def test_next_steps_after_partial_withdrawal(self):
        record_withdrawal(
            self.tenant,
            self.user,
            partner=self.anvar,
            amount=Decimal("100000"),
        )
        ledger = build_partner_ledger(self.tenant)
        keys = {s["key"] for s in ledger["next_steps"]}
        self.assertIn("partial", keys)
        self.assertIn("withdraw", keys)
        self.assertFalse(ledger["ready_to_reset"])

    def test_restart_today_option(self):
        closed, fresh = reset_profit_period(
            self.tenant, self.user, restart_today=True
        )
        # Davr bugundan boshlangan stub → ertadan toza start
        self.assertEqual(fresh.started_on, closed.ended_on + timedelta(days=1))

    def test_restart_today_splits_prior_days(self):
        """Ko‘p kunlik davr: yopiq kechagacha, yangi bugundan."""
        period = ensure_open_period(self.tenant)
        period.started_on = self.today - timedelta(days=2)
        period.save(update_fields=["started_on", "updated_at"])
        closed, fresh = reset_profit_period(
            self.tenant, self.user, restart_today=True
        )
        self.assertEqual(closed.ended_on, self.today - timedelta(days=1))
        self.assertEqual(fresh.started_on, self.today)

    def test_loss_period_does_not_assign_negative_shares(self):
        cat = ExpenseCategory.objects.get(tenant=self.tenant, name="Ops")
        Expense.objects.create(
            tenant=self.tenant,
            hotel=self.prop,
            category=cat,
            title="Katta rasxod",
            amount=Decimal("5000000"),
            expense_date=self.today,
            status=Expense.Status.PAID,
            created_by=self.user,
        )
        ledger = build_partner_ledger(self.tenant)
        # 1_000_000 − 200_000 − 5_000_000 = −4_200_000
        self.assertLess(ledger["net"], Decimal("0"))
        self.assertEqual(ledger["entitled_total"], Decimal("0.00"))
        self.assertEqual(ledger["distributable"], Decimal("0.00"))
        for row in ledger["rows"]:
            self.assertEqual(row["entitled"], Decimal("0.00"))
            self.assertEqual(row["remaining"], Decimal("0.00"))
        keys = {s["key"] for s in ledger["next_steps"]}
        self.assertIn("period_loss", keys)
    def test_profit_share_page(self):
        url = reverse("finance:profit_share")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Anvar")
        self.assertContains(resp, "Keyingi qadamlar")
        self.assertContains(resp, "Chek hisobot")
        self.assertContains(resp, "Sof foyda hisobi")

    def test_profit_share_receipt_print(self):
        url = reverse("finance:profit_share_print")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "chek hisobot")
        self.assertContains(resp, "Chop etish")
        ledger = resp.context["ledger"]
        self.assertIn("receipt", ledger)
        self.assertEqual(len(ledger["receipt"]["sections"]), 2)
        # Sof lines include revenue and net
        sof_labels = " ".join(l["label"] for l in ledger["receipt"]["sections"][0]["lines"])
        self.assertIn("Tushum", sof_labels)
        self.assertIn("Sof foyda", sof_labels)

    def test_closed_period_saves_receipt_snapshot(self):
        closed, fresh = reset_profit_period(self.tenant, self.user, restart_today=True)
        self.assertIsNotNone(closed.receipt_snapshot)
        self.assertIn("receipt", closed.receipt_snapshot)
        self.assertIsNotNone(closed.revenue_snapshot)
        hist = self.client.get(reverse("finance:profit_history"))
        self.assertEqual(hist.status_code, 200)
        self.assertContains(hist, "Tarix")
        detail = self.client.get(reverse("finance:profit_period_detail", args=[closed.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(detail.context["ledger"]["from_snapshot"])
        print_resp = self.client.get(
            reverse("finance:profit_share_print"), {"period": closed.pk}
        )
        self.assertEqual(print_resp.status_code, 200)
        self.assertContains(print_resp, "Chop etish")
