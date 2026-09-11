from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from bookings.commission import (
    build_commission_report,
    reservation_commission_amount,
    reservation_commission_base,
)
from bookings.models import BookingReferrer, Reservation
from bookings.services import create_reservation
from core.tests.helpers import setup_tenant_user
from folio.models import Folio, FolioCharge
from guests.models import Guest
from properties.models import Property, RatePlan, Room, RoomType


class CommissionReportTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(username="comm_user")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.prop = Property.objects.create(tenant=self.tenant, name="Demo Hotel")
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Standard",
            code="std",
            base_price=Decimal("1000000"),
        )
        self.room = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="201"
        )
        self.rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="BAR",
            code="bar",
            price=Decimal("1000000"),
        )
        self.guest = Guest.objects.create(
            tenant=self.tenant, first_name="Ali", last_name="Valiyev"
        )
        self.vali = BookingReferrer.objects.create(
            tenant=self.tenant,
            name="Vali",
            default_commission_percent=Decimal("15"),
        )
        self.today = timezone.localdate()

    def test_create_defaults_percent_from_referrer(self):
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
            referrer=self.vali,
        )
        self.assertEqual(reservation.referrer_id, self.vali.pk)
        self.assertEqual(reservation.commission_percent, Decimal("15"))
        self.assertEqual(
            reservation_commission_amount(reservation),
            (reservation.total_amount * Decimal("15") / Decimal("100")).quantize(
                Decimal("0.01")
            ),
        )

    def test_create_without_referrer_ok(self):
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
            commission_percent=Decimal("10"),  # ignored when no referrer
        )
        self.assertIsNone(reservation.referrer_id)
        self.assertIsNone(reservation.commission_percent)
        self.assertEqual(reservation_commission_amount(reservation), Decimal("0"))

    def test_commission_uses_room_folio_charges(self):
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
            referrer=self.vali,
            commission_percent=Decimal("10"),
            nightly_rate=Decimal("2000000"),
        )
        folio = Folio.objects.create(tenant=self.tenant, reservation=reservation)
        FolioCharge.objects.create(
            tenant=self.tenant,
            folio=folio,
            charge_type=FolioCharge.ChargeType.ROOM,
            description="Room",
            quantity=Decimal("1"),
            unit_price=Decimal("2000000"),
            posted_by=self.user,
        )
        FolioCharge.objects.create(
            tenant=self.tenant,
            folio=folio,
            charge_type=FolioCharge.ChargeType.MINIBAR,
            description="Minibar",
            quantity=Decimal("1"),
            unit_price=Decimal("50000"),
            posted_by=self.user,
        )
        reservation.refresh_from_db()
        self.assertEqual(reservation_commission_base(reservation), Decimal("2000000"))
        self.assertEqual(reservation_commission_amount(reservation), Decimal("200000.00"))

    def test_misc_room_charge_does_not_replace_actual_price(self):
        """Xato ROOM (beer/usluga) komissiyani faktik xona narxidan tortmasin."""
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
            referrer=self.vali,
            commission_percent=Decimal("15"),
            nightly_rate=Decimal("2000000"),
        )
        folio = Folio.objects.create(tenant=self.tenant, reservation=reservation)
        FolioCharge.objects.create(
            tenant=self.tenant,
            folio=folio,
            charge_type=FolioCharge.ChargeType.ROOM,
            description="beer",
            quantity=Decimal("10"),
            unit_price=Decimal("25000"),
            posted_by=self.user,
        )
        reservation.refresh_from_db()
        self.assertEqual(reservation_commission_base(reservation), Decimal("2000000"))
        self.assertEqual(reservation_commission_amount(reservation), Decimal("300000.00"))

    def test_duplicate_night_locale_does_not_double_commission(self):
        """Bir kecha ikki til/yozuv bilan chiqsa — komissiya bron summasidan."""
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
            referrer=self.vali,
            commission_percent=Decimal("10"),
            nightly_rate=Decimal("1000000"),
        )
        folio = Folio.objects.create(tenant=self.tenant, reservation=reservation)
        day = self.today.isoformat()
        FolioCharge.objects.create(
            tenant=self.tenant,
            folio=folio,
            charge_type=FolioCharge.ChargeType.ROOM,
            description=f"Night {day} — xona to‘lovi",
            quantity=Decimal("1"),
            unit_price=Decimal("1000000"),
            posted_by=self.user,
        )
        FolioCharge.objects.create(
            tenant=self.tenant,
            folio=folio,
            charge_type=FolioCharge.ChargeType.ROOM,
            description=f"Night {day} — плата за номер",
            quantity=Decimal("1"),
            unit_price=Decimal("1000000"),
            posted_by=self.user,
        )
        reservation.refresh_from_db()
        self.assertEqual(reservation.total_amount, Decimal("1000000"))
        self.assertEqual(reservation_commission_base(reservation), Decimal("1000000"))
        self.assertEqual(reservation_commission_amount(reservation), Decimal("100000.00"))

    def test_misc_room_charge_does_not_block_night_posts(self):
        from bookings.services import check_in_reservation
        from folio.services import ensure_stay_nights_posted

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
            nightly_rate=Decimal("2000000"),
        )
        from folio.services import open_folio_for_deposit

        folio = open_folio_for_deposit(reservation, self.user)
        # Depozit ochishda kecha allaqachon yoziladi
        self.assertEqual(
            folio.charges.filter(description__startswith="Night ").count(), 1
        )
        FolioCharge.objects.create(
            tenant=self.tenant,
            folio=folio,
            charge_type=FolioCharge.ChargeType.ROOM,
            description="beer",
            quantity=Decimal("1"),
            unit_price=Decimal("250000"),
            posted_by=self.user,
        )
        check_in_reservation(reservation, self.user)
        posted = ensure_stay_nights_posted(reservation, self.user)
        self.assertEqual(posted, 0)
        nights = folio.charges.filter(
            is_void=False, charge_type=FolioCharge.ChargeType.ROOM, description__startswith="Night "
        )
        self.assertEqual(nights.count(), 1)
        self.assertEqual(nights.first().amount, Decimal("2000000"))

    def test_monthly_report_groups_by_referrer(self):
        check_out = self.today.replace(day=15) if self.today.day >= 2 else self.today
        check_in = check_out - timedelta(days=1)
        res = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=check_in,
            check_out=check_out,
            referrer=self.vali,
            commission_percent=Decimal("15"),
        )
        res.status = Reservation.Status.CHECKED_OUT
        res.save(update_fields=["status", "updated_at"])
        # Hali chiqmagan bron Sof/komissiya hisobotiga kirmasin
        create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            rate_plan=self.rate,
            check_in=check_in,
            check_out=check_out,
            referrer=self.vali,
            commission_percent=Decimal("15"),
            status=Reservation.Status.CONFIRMED,
        )
        cancelled = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            rate_plan=self.rate,
            check_in=check_in,
            check_out=check_out,
            referrer=self.vali,
            commission_percent=Decimal("15"),
            status=Reservation.Status.CONFIRMED,
        )
        cancelled.status = Reservation.Status.CANCELLED
        cancelled.save(update_fields=["status"])

        report = build_commission_report(
            self.tenant, year=check_out.year, month=check_out.month
        )
        self.assertEqual(report["reservation_count"], 1)
        self.assertEqual(report["referrer_count"], 1)
        group = report["groups"][0]
        self.assertEqual(group["referrer"].name, "Vali")
        self.assertEqual(group["count"], 1)
        self.assertGreater(group["commission_total"], Decimal("0"))
        self.assertEqual(group["paid_total"], Decimal("0"))
        self.assertEqual(group["remaining"], group["commission_total"])

    def test_commission_payment_reduces_remaining(self):
        from django.urls import reverse

        from bookings.commission import record_commission_payment

        check_out = self.today.replace(day=15) if self.today.day >= 15 else self.today
        check_in = check_out - timedelta(days=1)
        res = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=check_in,
            check_out=check_out,
            referrer=self.vali,
            commission_percent=Decimal("10"),
        )
        res.status = Reservation.Status.CHECKED_OUT
        res.save(update_fields=["status", "updated_at"])
        report = build_commission_report(
            self.tenant, year=check_out.year, month=check_out.month
        )
        owed = report["groups"][0]["commission_total"]
        half = (owed / 2).quantize(Decimal("0.01"))
        record_commission_payment(
            self.tenant,
            self.vali,
            year=check_out.year,
            month=check_out.month,
            amount=half,
            user=self.user,
        )
        report2 = build_commission_report(
            self.tenant, year=check_out.year, month=check_out.month
        )
        g = report2["groups"][0]
        self.assertEqual(g["paid_total"], half)
        self.assertEqual(g["remaining"], owed - half)

        self.client.force_login(self.user)
        resp = self.client.post(
            reverse("bookings:commission_pay", args=[self.vali.pk]),
            {
                "year": check_out.year,
                "month": check_out.month,
                "amount": str(g["remaining"]),
                "currency": "UZS",
                "paid_on": check_out.isoformat(),
                "method": "cash",
                "note": "Qoldiq",
            },
        )
        self.assertEqual(resp.status_code, 302)
        report3 = build_commission_report(
            self.tenant, year=check_out.year, month=check_out.month
        )
        self.assertEqual(report3["groups"][0]["remaining"], Decimal("0"))

    def test_commission_pay_form_fields_present_on_page(self):
        """Template must expose every CommissionPaymentForm field (anti-drift)."""
        from django.urls import reverse

        from bookings.forms import CommissionPaymentForm

        check_out = self.today.replace(day=15) if self.today.day >= 2 else self.today
        check_in = check_out - timedelta(days=1)
        res = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=check_in,
            check_out=check_out,
            referrer=self.vali,
            commission_percent=Decimal("10"),
        )
        res.status = Reservation.Status.CHECKED_OUT
        res.save(update_fields=["status", "updated_at"])
        self.client.force_login(self.user)
        resp = self.client.get(
            reverse("bookings:commission_report"),
            {"year": check_out.year, "month": check_out.month},
        )
        self.assertEqual(resp.status_code, 200)
        for name in CommissionPaymentForm.base_fields:
            self.assertContains(resp, f'name="{name}"')

    def test_commission_pay_works_without_currency_posted(self):
        """Missing currency must default to tenant currency, not fail silently."""
        from django.urls import reverse

        check_out = self.today.replace(day=15) if self.today.day >= 2 else self.today
        check_in = check_out - timedelta(days=1)
        res = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=check_in,
            check_out=check_out,
            referrer=self.vali,
            commission_percent=Decimal("10"),
        )
        res.status = Reservation.Status.CHECKED_OUT
        res.save(update_fields=["status", "updated_at"])
        self.client.force_login(self.user)
        report = build_commission_report(
            self.tenant, year=check_out.year, month=check_out.month
        )
        remaining = report["groups"][0]["remaining"]
        resp = self.client.post(
            reverse("bookings:commission_pay", args=[self.vali.pk]),
            {
                "year": check_out.year,
                "month": check_out.month,
                "amount": str(remaining),
                "paid_on": check_out.isoformat(),
                "method": "cash",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "saqlanmadi")
        report2 = build_commission_report(
            self.tenant, year=check_out.year, month=check_out.month
        )
        self.assertEqual(report2["groups"][0]["remaining"], Decimal("0"))

    def test_commission_statement_page(self):
        from django.urls import reverse

        check_out = self.today.replace(day=15) if self.today.day >= 2 else self.today
        check_in = check_out - timedelta(days=1)
        res = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=check_in,
            check_out=check_out,
            referrer=self.vali,
            commission_percent=Decimal("10"),
        )
        res.status = Reservation.Status.CHECKED_OUT
        res.save(update_fields=["status", "updated_at"])
        self.client.force_login(self.user)
        resp = self.client.get(
            reverse("bookings:commission_statement", args=[self.vali.pk]),
            {"year": check_out.year, "month": check_out.month},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Komissiya bayonnomasi")
        self.assertContains(resp, "Vali")
        self.assertContains(resp, "Chop etish")
        report_resp = self.client.get(
            reverse("bookings:commission_report"),
            {"year": check_out.year, "month": check_out.month},
        )
        self.assertContains(report_resp, "Bayonnoma")
        self.assertContains(
            report_resp,
            reverse("bookings:commission_statement", args=[self.vali.pk]),
        )
