from datetime import date, datetime, time, timedelta
from decimal import Decimal
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Reservation
from bookings.services import (
    check_in_reservation,
    check_out_reservation,
    create_group_booking,
    create_reservation,
)
from core.tests.helpers import setup_tenant_user
from folio.models import FolioCharge, GuestPayment
from folio.services import add_split_payments, open_folio_for_deposit, add_payment, collect_emehmon_fee
from guests.models import Guest
from properties.models import Property, PropertySettings, RatePlan, Room, RoomType
from subscriptions.models import Plan


class EarlyLateFeeTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="fees")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.prop = Property.objects.create(tenant=self.tenant, name="Fee Hotel")
        PropertySettings.objects.create(
            tenant=self.tenant,
            property=self.prop,
            early_checkin_fee=Decimal("50000"),
            late_checkout_fee=Decimal("75000"),
            checkin_time=time(14, 0),
            checkout_time=time(12, 0),
            require_id_on_checkin=False,
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
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Fee")
        self.today = timezone.localdate()

    def test_early_checkin_posts_fee(self):
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
        early = timezone.make_aware(datetime.combine(self.today, time(10, 0)))
        with mock.patch("bookings.services.timezone.now", return_value=early):
            check_in_reservation(reservation, self.user)
        fee = FolioCharge.objects.filter(
            folio__reservation=reservation, description__startswith="Erta joylash"
        ).first()
        self.assertIsNotNone(fee)
        self.assertEqual(fee.amount, Decimal("50000"))

    def test_late_checkout_posts_fee(self):
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
        on_time = timezone.make_aware(datetime.combine(self.today, time(15, 0)))
        with mock.patch("bookings.services.timezone.now", return_value=on_time):
            check_in_reservation(reservation, self.user)
        late = timezone.make_aware(
            datetime.combine(self.today + timedelta(days=1), time(15, 0))
        )
        from folio.services import add_payment, ensure_stay_nights_posted

        ensure_stay_nights_posted(reservation, self.user)
        add_payment(
            reservation.folio,
            self.user,
            amount=reservation.folio.balance,
            method="card",
        )
        with mock.patch("bookings.services.timezone.now", return_value=late):
            with self.assertRaises(ValidationError):
                check_out_reservation(reservation, self.user)
        fee = FolioCharge.objects.filter(
            folio__reservation=reservation, description__startswith="Kechikkan chiqish"
        ).first()
        self.assertIsNotNone(fee)
        self.assertEqual(fee.amount, Decimal("75000"))


class EmehmonFeeTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="emehmon")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.prop = Property.objects.create(tenant=self.tenant, name="Emehmon Hotel")
        PropertySettings.objects.create(
            tenant=self.tenant,
            property=self.prop,
            emehmon_fee=Decimal("9000"),
            require_id_on_checkin=False,
        )
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Std",
            code="std",
            base_price=Decimal("100000"),
        )
        self.room = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="301"
        )
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Ali")
        self.today = timezone.localdate()

    def test_default_fee_is_unit_times_nights_times_guests(self):
        from folio.services import default_emehmon_fee

        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            check_in=self.today,
            check_out=self.today + timedelta(days=3),
            adults=2,
            children=1,
        )
        # 9000 × 3 kecha × 3 mehmon
        self.assertEqual(default_emehmon_fee(reservation), Decimal("81000.00"))

    def test_collect_emehmon_at_booking(self):
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
            adults=1,
        )
        charge, payment = collect_emehmon_fee(
            reservation,
            self.user,
            method=GuestPayment.Method.CARD,
        )
        # 9000 × 2 kecha × 1 mehmon
        self.assertEqual(charge.amount, Decimal("18000.00"))
        self.assertEqual(charge.quantity, Decimal("2"))
        self.assertEqual(charge.unit_price, Decimal("9000"))
        self.assertEqual(charge.charge_type, FolioCharge.ChargeType.EMEHMON)
        self.assertEqual(payment.amount, Decimal("18000.00"))
        self.assertTrue(charge.description.startswith("E-mehmon"))
        with self.assertRaises(ValidationError):
            collect_emehmon_fee(reservation, self.user, method=GuestPayment.Method.CARD)

    def test_monthly_emehmon_report(self):
        from bookings.emehmon import build_emehmon_report

        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            check_in=self.today.replace(day=1),
            check_out=self.today.replace(day=1) + timedelta(days=2),
            adults=2,
        )
        collect_emehmon_fee(reservation, self.user, method=GuestPayment.Method.CARD)
        report = build_emehmon_report(
            self.tenant, year=self.today.year, month=self.today.month
        )
        self.assertEqual(report["total_guest_nights"], 4)  # 2 nights × 2 guests
        self.assertEqual(report["total_expected"], Decimal("36000.00"))
        self.assertEqual(report["total_collected"], Decimal("36000.00"))
        self.assertEqual(len(report["collections"]), 1)
        self.assertEqual(report["collections"][0]["amount"], Decimal("36000.00"))

    def test_emehmon_statement_page(self):
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
            adults=1,
        )
        collect_emehmon_fee(reservation, self.user, method=GuestPayment.Method.CARD)
        self.client.force_login(self.user)
        resp = self.client.get(
            reverse("bookings:emehmon_statement"),
            {"year": self.today.year, "month": self.today.month},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "E-mehmon bayonnomasi")
        self.assertContains(resp, "9 000")
        self.assertContains(resp, "Jami olingan")
        self.assertContains(resp, "E-mehmonga topshirish")

    def test_emehmon_report_hides_tarif_columns(self):
        self.client.force_login(self.user)
        resp = self.client.get(
            reverse("bookings:emehmon_report"),
            {"year": self.today.year, "month": self.today.month},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, ">Tarif<")
        self.assertNotContains(resp, ">Hisoblangan<")
        self.assertContains(resp, "Bayonnoma / chek")
        self.assertContains(resp, "Olingan")

    def test_cross_month_collected_is_prorated(self):
        """Olingan summa oy kechalariga proporsional — P&L farqi to‘g‘ri."""
        from bookings.emehmon import emehmon_totals_for_range
        from calendar import monthrange

        # Oxirgi oy oxiri → shu oy: 4 kecha; faqat 9000 olingan
        if self.today.month == 1:
            check_in = date(self.today.year - 1, 12, 30)
        else:
            prev = self.today.month - 1
            last_prev = monthrange(self.today.year, prev)[1]
            check_in = date(self.today.year, prev, last_prev)
        check_out = check_in + timedelta(days=4)
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            check_in=check_in,
            check_out=check_out,
            adults=1,
        )
        collect_emehmon_fee(
            reservation,
            self.user,
            amount=Decimal("9000"),
            method=GuestPayment.Method.CARD,
        )
        m_start = self.today.replace(day=1)
        m_end = self.today.replace(day=monthrange(self.today.year, self.today.month)[1])
        cur = emehmon_totals_for_range(self.tenant, m_start, m_end)
        row = next(r for r in cur["rows"] if r["reservation"].pk == reservation.pk)
        nights_cur = row["nights_in_month"]
        self.assertGreater(nights_cur, 0)
        expected_share = (Decimal("9000") * Decimal(nights_cur) / Decimal("4")).quantize(
            Decimal("0.01")
        )
        self.assertEqual(row["collected"], expected_share)
        self.assertEqual(row["expected"], Decimal(9000 * nights_cur))
        self.assertEqual(
            row["gap"],
            (Decimal(9000 * nights_cur) - expected_share).quantize(Decimal("0.01")),
        )

    def test_emehmon_optional_not_required_skips_expected(self):
        from bookings.emehmon import build_emehmon_report

        create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
            adults=2,
            emehmon_required=False,
        )
        report = build_emehmon_report(
            self.tenant, year=self.today.year, month=self.today.month
        )
        self.assertEqual(report["total_expected"], Decimal("0"))
        self.assertEqual(report["total_gap"], Decimal("0"))

    def test_collect_sets_emehmon_required(self):
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
            adults=1,
            emehmon_required=False,
        )
        self.assertFalse(reservation.emehmon_required)
        collect_emehmon_fee(reservation, self.user, method=GuestPayment.Method.CARD)
        reservation.refresh_from_db()
        self.assertTrue(reservation.emehmon_required)

    def test_form_collect_emehmon_defaults_on(self):
        from bookings.forms import ReservationForm, WalkInForm

        rf = ReservationForm(tenant=self.tenant, hotel=self.prop)
        wf = WalkInForm(tenant=self.tenant, hotel=self.prop)
        self.assertNotIn("collect_emehmon", rf.fields)
        self.assertIs(wf.fields["collect_emehmon"].initial, True)

    def test_check_in_collects_emehmon_when_checked(self):
        from folio.models import FolioCharge
        from folio.services import emehmon_already_posted

        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
            adults=1,
            emehmon_required=False,
        )
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse("bookings:check_in", args=[reservation.pk]),
            {
                "collect_emehmon": "1",
                "emehmon_amount": "9000",
                "emehmon_method": "card",
            },
        )
        self.assertEqual(resp.status_code, 302)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CHECKED_IN)
        self.assertTrue(reservation.emehmon_required)
        self.assertTrue(emehmon_already_posted(reservation.folio))
        self.assertTrue(
            reservation.folio.charges.filter(
                charge_type=FolioCharge.ChargeType.EMEHMON, is_void=False
            ).exists()
        )

    def test_check_in_skips_emehmon_when_unchecked(self):
        from folio.services import emehmon_already_posted

        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
            adults=1,
            emehmon_required=True,
        )
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse("bookings:check_in", args=[reservation.pk]),
            {},
        )
        self.assertEqual(resp.status_code, 302)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CHECKED_IN)
        self.assertFalse(reservation.emehmon_required)
        self.assertFalse(emehmon_already_posted(reservation.folio))

    def test_emehmon_required_unpaid_counts_shortfall(self):
        from bookings.emehmon import build_emehmon_report

        create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
            adults=1,
            emehmon_required=True,
        )
        report = build_emehmon_report(
            self.tenant, year=self.today.year, month=self.today.month
        )
        self.assertEqual(report["total_expected"], Decimal("18000.00"))
        self.assertEqual(report["total_collected"], Decimal("0"))
        self.assertEqual(report["total_gap"], Decimal("18000.00"))

    def test_usd_payment_converts_to_base(self):
        from tenants.models import ExchangeRate

        ExchangeRate.objects.create(
            tenant=self.tenant,
            currency="USD",
            base_currency="UZS",
            rate=Decimal("10000"),
            effective_on=self.today,
        )
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
        )
        from folio.services import open_folio_for_deposit, add_payment

        folio = open_folio_for_deposit(reservation, self.user)
        pay = add_payment(
            folio,
            self.user,
            amount=Decimal("10"),
            method=GuestPayment.Method.CARD,
            currency="USD",
        )
        self.assertEqual(pay.currency, "USD")
        self.assertEqual(pay.fx_rate, Decimal("10000"))
        self.assertEqual(pay.amount_base, Decimal("100000"))
        self.assertEqual(folio.payments_total, Decimal("100000"))


class DepositSplitGroupTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="dsg")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.prop = Property.objects.create(tenant=self.tenant, name="Group Hotel")
        PropertySettings.objects.create(tenant=self.tenant, property=self.prop,
            require_id_on_checkin=False,
        )
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Std",
            code="std",
            base_price=Decimal("100000"),
        )
        self.room1 = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="201"
        )
        self.room2 = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="202"
        )
        self.guest1 = Guest.objects.create(tenant=self.tenant, first_name="A")
        self.guest2 = Guest.objects.create(tenant=self.tenant, first_name="B")
        self.today = timezone.localdate()

    def test_deposit_before_checkin(self):
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest1,
            room_type=self.rt,
            room=self.room1,
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
        )
        folio = open_folio_for_deposit(reservation, self.user)
        add_payment(
            folio,
            self.user,
            amount=Decimal("30000"),
            kind=GuestPayment.Kind.DEPOSIT,
            method=GuestPayment.Method.CARD,
        )
        self.assertEqual(folio.payments.filter(kind=GuestPayment.Kind.DEPOSIT).count(), 1)
        from bookings.models import Stay

        self.assertFalse(Stay.objects.filter(reservation=reservation).exists())

    def test_split_payments(self):
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest1,
            room_type=self.rt,
            room=self.room1,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
        )
        folio = open_folio_for_deposit(reservation, self.user)
        from folio.services import open_cash_shift

        open_cash_shift(self.tenant, self.user, Decimal("0"), hotel=self.prop)
        add_split_payments(
            folio,
            self.user,
            [
                {"amount": Decimal("40000"), "method": GuestPayment.Method.CASH},
                {"amount": Decimal("60000"), "method": GuestPayment.Method.CARD},
            ],
        )
        self.assertEqual(folio.payments.count(), 2)
        self.assertEqual(folio.payments_total, Decimal("100000"))

    def test_group_booking(self):
        group, created = create_group_booking(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            name="Tour group",
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
            rooms_data=[
                {"guest": self.guest1, "room_type": self.rt, "room": self.room1},
                {"guest": self.guest2, "room_type": self.rt, "room": self.room2},
            ],
        )
        self.assertEqual(len(created), 2)
        self.assertEqual(group.reservations.count(), 2)
        self.assertTrue(group.code.startswith("GRP-"))
