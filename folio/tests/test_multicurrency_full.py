"""Cross-module multi-currency (UZS/USD/EUR) accounting checks."""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from bookings.commission import reservation_commission_base, reservation_commission_amount
from bookings.models import BookingReferrer
from bookings.services import create_reservation
from core.tests.helpers import setup_tenant_user
from folio.models import FolioCharge, GuestPayment
from folio.services import add_charge, add_payment, open_folio_for_deposit
from guests.models import Guest
from properties.models import Property, PropertySettings, RatePlan, Room, RoomType
from reports.accounting import cash_pnl_for_range, inventory_cost_in_range
from subscriptions.models import Plan
from tenants.models import ExchangeRate


class FullMultiCurrencyAccountingTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="fxfull")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.tenant.currency = "UZS"
        self.tenant.save(update_fields=["currency"])
        self.prop = Property.objects.create(tenant=self.tenant, name="FX Hotel")
        PropertySettings.objects.create(
            tenant=self.tenant, property=self.prop, require_id_on_checkin=False
        )
        ExchangeRate.objects.create(
            tenant=self.tenant,
            currency="USD",
            base_currency="UZS",
            rate=Decimal("10000"),
            effective_on=timezone.localdate(),
        )
        ExchangeRate.objects.create(
            tenant=self.tenant,
            currency="EUR",
            base_currency="UZS",
            rate=Decimal("11000"),
            effective_on=timezone.localdate(),
        )
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Deluxe",
            code="dlx",
            base_price=Decimal("50"),
            currency="USD",
        )
        self.rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="BAR USD",
            code="bar-usd",
            price=Decimal("50"),
            currency="USD",
            is_default=True,
        )
        self.room = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="701"
        )
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="FX")
        self.today = timezone.localdate()

    def test_mixed_currency_folio_balance_and_pnl(self):
        reservation = create_reservation(
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
        self.assertEqual(reservation.currency, "USD")
        folio = open_folio_for_deposit(reservation, self.user)
        # open_folio_for_deposit allaqachon kecha to‘lovini yozadi (50 USD)
        self.assertEqual(folio.charges_total, Decimal("500000"))
        add_payment(
            folio,
            self.user,
            amount=Decimal("40"),
            method=GuestPayment.Method.CARD,
            currency="EUR",
        )
        # 50 USD = 500_000 UZS; 40 EUR = 440_000 UZS → balance 60_000
        self.assertEqual(folio.charges_total, Decimal("500000"))
        self.assertEqual(folio.payments_total, Decimal("440000"))
        self.assertEqual(folio.balance, Decimal("60000"))

        pnl = cash_pnl_for_range(self.tenant, self.today, self.today)
        self.assertEqual(pnl["revenue_total"], Decimal("440000"))

    def test_commission_uses_amount_base(self):
        ref = BookingReferrer.objects.create(
            tenant=self.tenant, name="Agent", default_commission_percent=Decimal("10")
        )
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
            referrer=ref,
            commission_percent=Decimal("10"),
        )
        folio = open_folio_for_deposit(reservation, self.user)
        # Kecha allaqachon yozilgan — qo‘shimcha ROOM kerak emas
        self.assertEqual(folio.charges_total, Decimal("500000"))
        base = reservation_commission_base(reservation)
        self.assertEqual(base, Decimal("500000"))
        self.assertEqual(reservation_commission_amount(reservation), Decimal("50000"))

    def test_inventory_cost_converts_currency(self):
        from inventory.models import StockItem, StockMovement
        from inventory.services import adjust_stock

        item = StockItem.objects.create(
            tenant=self.tenant,
            hotel=self.prop,
            name="Wine",
            sku="wine-1",
            unit_cost=Decimal("10"),
            sell_price=Decimal("20"),
            currency="USD",
            quantity_on_hand=Decimal("0"),
        )
        adjust_stock(
            item,
            movement_type=StockMovement.MovementType.IN,
            quantity=Decimal("2"),
            user=self.user,
            note="buy",
        )
        cost = inventory_cost_in_range(self.tenant, self.today, self.today)
        self.assertEqual(cost, Decimal("200000"))  # 2 * 10 USD * 10000

    def test_refund_foreign_currency_uses_base_credit(self):
        from folio.services import refund_overpayment

        reservation = create_reservation(
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
        folio = open_folio_for_deposit(reservation, self.user)
        # 50 USD kecha allaqachon yozilgan; 60 USD to‘lov → credit 10 USD
        add_payment(
            folio,
            self.user,
            amount=Decimal("60"),
            method=GuestPayment.Method.CARD,
            currency="USD",
        )
        self.assertEqual(folio.credit_amount, Decimal("100000"))
        refund_overpayment(
            folio,
            self.user,
            amount=Decimal("10"),
            currency="USD",
            method=GuestPayment.Method.CARD,
        )
        folio.refresh_from_db()
        self.assertEqual(folio.credit_amount, Decimal("0"))

    def test_timing_fee_posts_in_tenant_currency(self):
        from bookings.services import _post_timing_fee

        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
            currency="USD",
            nightly_rate=Decimal("50"),
        )
        folio = open_folio_for_deposit(reservation, self.user)
        charge = _post_timing_fee(
            folio,
            self.user,
            amount=Decimal("75000"),
            description="before 14:00",
            marker="Erta joylash to‘lovi",
        )
        self.assertIsNotNone(charge)
        self.assertEqual(charge.currency, "UZS")
        self.assertEqual(charge.amount, Decimal("75000"))
        self.assertEqual(charge.amount_base, Decimal("75000"))

    def test_legacy_prepaid_compares_quote_in_base(self):
        from folio.services import ensure_stay_nights_posted, folio_has_legacy_prepaid_room

        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
            currency="USD",
            nightly_rate=Decimal("50"),
        )
        folio = open_folio_for_deposit(reservation, self.user)
        # open_folio_for_deposit kechalarni yozadi — qayta chaqiriq 0 qaytaradi
        self.assertFalse(folio_has_legacy_prepaid_room(folio))
        self.assertEqual(folio.charges.filter(description__startswith="Night ").count(), 1)
        posted = ensure_stay_nights_posted(reservation, self.user)
        self.assertEqual(posted, 0)
        # Kichik «beer» ROOM yozuvi night postingni bloklamasligi kerak edi (allaqachon yozilgan)
        add_charge(
            folio,
            self.user,
            charge_type=FolioCharge.ChargeType.ROOM,
            description="beer",
            unit_price=Decimal("5000"),
            currency="UZS",
        )
        self.assertFalse(folio_has_legacy_prepaid_room(folio))
