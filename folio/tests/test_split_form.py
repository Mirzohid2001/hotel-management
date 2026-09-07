from decimal import Decimal

from django.test import TestCase

from folio.forms import SplitPaymentForm
from folio.models import GuestPayment


class SplitPaymentFormTests(TestCase):
    def test_single_line(self):
        form = SplitPaymentForm(
            data={
                "method": [GuestPayment.Method.CASH],
                "amount": ["50000"],
                "kind": [GuestPayment.Kind.PAYMENT],
                "note": "test",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        lines = form.lines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["amount"], Decimal("50000"))
        self.assertEqual(lines[0]["method"], GuestPayment.Method.CASH)

    def test_dynamic_multiple_lines_skips_zeros(self):
        form = SplitPaymentForm(
            data={
                "method": [
                    GuestPayment.Method.CASH,
                    GuestPayment.Method.CARD,
                    GuestPayment.Method.TRANSFER,
                ],
                "amount": ["40000", "0", "60000"],
                "kind": [
                    GuestPayment.Kind.PAYMENT,
                    GuestPayment.Kind.PAYMENT,
                    GuestPayment.Kind.DEPOSIT,
                ],
                "note": "",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        lines = form.lines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["amount"], Decimal("40000"))
        self.assertEqual(lines[1]["amount"], Decimal("60000"))
        self.assertEqual(lines[1]["kind"], GuestPayment.Kind.DEPOSIT)

    def test_requires_at_least_one_positive(self):
        form = SplitPaymentForm(
            data={
                "method": [GuestPayment.Method.CASH],
                "amount": ["0"],
                "kind": [GuestPayment.Kind.PAYMENT],
            }
        )
        self.assertFalse(form.is_valid())
