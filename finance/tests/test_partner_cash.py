from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from core.tests.helpers import setup_tenant_user
from finance.models import PartnerCashHandover, ProfitPartner
from finance.partner_cash import (
    build_partner_cash_board,
    confirm_handover,
    create_handover,
    holder_balance,
    record_cash_spend,
)
from finance.profit import build_partner_ledger
from subscriptions.models import Plan


class PartnerCashFlowTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="pcash")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        self.a = ProfitPartner.objects.create(
            tenant=self.tenant, name="Eshmat", share_percent=Decimal("50")
        )
        self.b = ProfitPartner.objects.create(
            tenant=self.tenant, name="Toshmat", share_percent=Decimal("50")
        )

    def test_handover_confirm_spend_balance(self):
        h = create_handover(
            self.tenant,
            self.user,
            from_partner=self.a,
            to_partner=self.b,
            amount=Decimal("1000000"),
        )
        self.assertEqual(h.status, PartnerCashHandover.Status.PENDING)
        self.assertEqual(holder_balance(self.tenant, self.b)["remaining"], Decimal("0.00"))

        confirm_handover(self.tenant, self.user, h, confirmed_amount=Decimal("1000000"))
        bal = holder_balance(self.tenant, self.b)
        self.assertEqual(bal["received"], Decimal("1000000.00"))
        self.assertEqual(bal["remaining"], Decimal("1000000.00"))

        record_cash_spend(
            self.tenant,
            self.user,
            holder=self.b,
            title="Bozor",
            amount=Decimal("250000"),
        )
        bal = holder_balance(self.tenant, self.b)
        self.assertEqual(bal["spent"], Decimal("250000.00"))
        self.assertEqual(bal["remaining"], Decimal("750000.00"))

    def test_does_not_touch_sof_foyda_ledger(self):
        before = build_partner_ledger(self.tenant)
        h = create_handover(
            self.tenant,
            self.user,
            from_partner=self.a,
            to_partner=self.b,
            amount=Decimal("500000"),
        )
        confirm_handover(self.tenant, self.user, h)
        record_cash_spend(
            self.tenant,
            self.user,
            holder=self.b,
            title="Taxi",
            amount=Decimal("100000"),
        )
        after = build_partner_ledger(self.tenant)
        self.assertEqual(before["net"], after["net"])
        self.assertEqual(before["distributable"], after["distributable"])

    def test_overspend_blocked(self):
        h = create_handover(
            self.tenant,
            self.user,
            from_partner=self.a,
            to_partner=self.b,
            amount=Decimal("100000"),
        )
        confirm_handover(self.tenant, self.user, h)
        with self.assertRaises(ValidationError):
            record_cash_spend(
                self.tenant,
                self.user,
                holder=self.b,
                title="Katta",
                amount=Decimal("200000"),
            )

    def test_board_page(self):
        url = reverse("finance:partner_cash")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Ulushdorlar")
        board = build_partner_cash_board(self.tenant)
        self.assertEqual(len(board["balances"]), 2)
