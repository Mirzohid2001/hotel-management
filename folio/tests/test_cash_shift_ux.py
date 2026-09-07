from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from core.tests.helpers import make_property_stack, setup_tenant_user
from folio.models import CashShiftMovement
from folio.services import (
    add_cash_movement,
    close_cash_shift,
    expected_cash_in_shift,
    get_open_shift,
    open_cash_shift,
)
from folio.shift_report import build_shift_report
from subscriptions.models import Plan


class CashShiftMovementTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="cashmove")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        stack = make_property_stack(self.tenant, room_number="C1")
        self.prop = stack["property"]

    def test_pay_in_out_affects_expected(self):
        shift = open_cash_shift(self.tenant, self.user, Decimal("100000"), hotel=self.prop)
        add_cash_movement(
            shift, self.user, kind=CashShiftMovement.Kind.PAY_IN, amount=Decimal("20000"), note="bank"
        )
        add_cash_movement(
            shift, self.user, kind=CashShiftMovement.Kind.PAY_OUT, amount=Decimal("5000"), note="taxi"
        )
        report = build_shift_report(shift)
        self.assertEqual(report["movements"]["pay_in"], Decimal("20000"))
        self.assertEqual(report["movements"]["pay_out"], Decimal("5000"))
        self.assertEqual(expected_cash_in_shift(shift), Decimal("115000"))
        closed = close_cash_shift(shift, self.user, Decimal("115000"))
        self.assertEqual(closed.variance, Decimal("0"))

    def test_movement_blocked_when_closed(self):
        shift = open_cash_shift(self.tenant, self.user, Decimal("0"), hotel=self.prop)
        close_cash_shift(shift, self.user, Decimal("0"))
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            add_cash_movement(
                shift, self.user, kind=CashShiftMovement.Kind.PAY_IN, amount=Decimal("1000")
            )

    def test_movement_post_and_print(self):
        open_cash_shift(self.tenant, self.user, Decimal("50000"), hotel=self.prop)
        url = reverse("folio:cash_shift_movement")
        resp = self.client.post(
            url,
            {"kind": "pay_out", "amount": "1500", "currency": "UZS", "note": "mayda"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        shift = get_open_shift(self.tenant, hotel=self.prop)
        self.assertEqual(shift.movements.count(), 1)
        closed = close_cash_shift(shift, self.user, Decimal("48500"))
        print_url = reverse("folio:cash_shift_print", kwargs={"pk": closed.pk})
        print_resp = self.client.get(print_url)
        self.assertEqual(print_resp.status_code, 200)
        self.assertContains(print_resp, "mayda")
        detail = self.client.get(reverse("folio:cash_shift_detail", kwargs={"pk": closed.pk}))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Chop etish")
