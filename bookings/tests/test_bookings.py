from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import BookingReferrer, Reservation, ReservationOccupant
from bookings.services import (
    AvailabilityError,
    apply_amendment,
    check_in_reservation,
    check_out_reservation,
    create_reservation,
)
from core.models import ActivityLog
from core.tests.helpers import setup_tenant_user
from folio.models import CashShift, CompanyInvoice, CompanyInvoiceLine, Folio, GuestPayment
from guests.models import Company, Guest
from properties.models import Property, RatePlan, Room, RoomType


class BookingFlowTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(username="booker")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.prop = Property.objects.create(tenant=self.tenant, name="Demo Hotel")
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Standard",
            code="std",
            base_price=Decimal("300000"),
        )
        self.room = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="101"
        )
        self.room_b = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="102"
        )
        self.rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="BAR",
            code="bar",
            price=Decimal("300000"),
        )
        self.guest = Guest.objects.create(
            tenant=self.tenant, first_name="Ali", last_name="Karimov", phone="90111"
        )
        self.today = timezone.localdate()

    def test_amend_availability_ignores_own_stay(self):
        self.client.force_login(self.user)
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=4),
        )
        shortened = self.today + timedelta(days=3)
        url = reverse("bookings:availability")
        blocked = self.client.get(
            url,
            {"room": self.room.pk, "check_in": self.today.isoformat(), "check_out": shortened.isoformat()},
        )
        self.assertContains(blocked, "band")
        free = self.client.get(
            url,
            {
                "room": self.room.pk,
                "check_in": self.today.isoformat(),
                "check_out": shortened.isoformat(),
                "exclude": reservation.pk,
            },
        )
        self.assertContains(free, "bo‘sh")
        self.assertNotContains(free, "band")

    def test_overlap_blocked(self):
        create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
        )
        with self.assertRaises(AvailabilityError):
            create_reservation(
                tenant=self.tenant,
                user=self.user,
                property_obj=self.prop,
                guest=self.guest,
                room_type=self.rt,
                room=self.room,
                rate_plan=self.rate,
                check_in=self.today + timedelta(days=1),
                check_out=self.today + timedelta(days=3),
            )

    def test_same_day_turnover_allowed(self):
        """Checkout day is free: 18→20 then new guest from 20 is OK."""
        create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
        )
        next_guest = Guest.objects.create(
            tenant=self.tenant, first_name="Next", last_name="Guest", phone="90222"
        )
        second = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=next_guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today + timedelta(days=2),
            check_out=self.today + timedelta(days=4),
        )
        self.assertEqual(second.check_in, self.today + timedelta(days=2))
        self.assertEqual(second.nights, 2)

    def test_check_in_out_and_dirty(self):
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
        check_in_reservation(reservation, self.user)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CHECKED_IN)
        from folio.services import add_payment, ensure_stay_nights_posted

        ensure_stay_nights_posted(reservation, self.user)
        add_payment(
            reservation.folio,
            self.user,
            amount=reservation.folio.balance,
            method=GuestPayment.Method.CARD,
        )
        check_out_reservation(reservation, self.user)
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, Room.Status.DIRTY)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CHECKED_OUT)

    def test_amend_extends_and_logs(self):
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
        apply_amendment(
            reservation,
            self.user,
            {
                "check_in": self.today,
                "check_out": self.today + timedelta(days=3),
                "room": self.room,
                "nightly_rate": Decimal("300000"),
                "adults": 2,
                "children": 0,
                "reason": "guest asked",
            },
        )
        reservation.refresh_from_db()
        self.assertEqual(reservation.nights, 3)
        self.assertEqual(reservation.nightly_rate, Decimal("300000"))
        self.assertIsNone(reservation.rate_plan_id)
        self.assertEqual(reservation.total_amount, Decimal("900000"))
        self.assertTrue(reservation.change_logs.filter(field="check_out").exists())

    def test_amend_updates_referrer_guest_source(self):
        other = Guest.objects.create(
            tenant=self.tenant, first_name="Nodira", last_name="Aliyeva", phone="90222"
        )
        company = Company.objects.create(tenant=self.tenant, name="Tour LLC")
        referrer = BookingReferrer.objects.create(
            tenant=self.tenant, name="Vali", default_commission_percent=Decimal("10")
        )
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            nightly_rate=Decimal("200000"),
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
        )
        apply_amendment(
            reservation,
            self.user,
            {
                "check_in": self.today,
                "check_out": self.today + timedelta(days=1),
                "room": self.room,
                "nightly_rate": Decimal("200000"),
                "adults": 1,
                "children": 0,
                "guest": other,
                "company": company,
                "referrer": referrer,
                "commission_percent": Decimal("12"),
                "source": Reservation.Source.WEBSITE,
                "notes": "from site",
                "reason": "missed fields",
            },
        )
        reservation.refresh_from_db()
        self.assertEqual(reservation.guest_id, other.pk)
        self.assertEqual(reservation.company_id, company.pk)
        self.assertEqual(reservation.referrer_id, referrer.pk)
        self.assertEqual(reservation.commission_percent, Decimal("12"))
        self.assertEqual(reservation.source, Reservation.Source.WEBSITE)
        self.assertEqual(reservation.notes, "from site")
        self.assertTrue(reservation.change_logs.filter(field="referrer").exists())

    def test_amend_page_exposes_create_fields(self):
        self.client.force_login(self.user)
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            nightly_rate=Decimal("200000"),
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
        )
        resp = self.client.get(reverse("bookings:amend", args=[reservation.pk]))
        self.assertEqual(resp.status_code, 200)
        for name in (
            "guest",
            "company",
            "referrer",
            "commission_percent",
            "source",
            "notes",
            "check_in",
            "currency",
            "nightly_rate",
        ):
            self.assertContains(resp, f'name="{name}"')

    def test_manual_nightly_rate_sets_total(self):
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            nightly_rate=Decimal("250000"),
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
        )
        self.assertEqual(reservation.nightly_rate, Decimal("250000"))
        self.assertIsNone(reservation.rate_plan_id)
        self.assertEqual(reservation.total_amount, Decimal("500000"))
        from folio.services import night_amount_for

        self.assertEqual(night_amount_for(reservation, self.today), Decimal("250000"))

    def test_check_in_without_room_fails(self):
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=None,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
        )
        with self.assertRaises(ValidationError):
            check_in_reservation(reservation, self.user)

    def test_admin_purge_deletes_only_that_booking(self):
        from tenants.models import TenantMembership

        self.client.force_login(self.user)
        later = self.today + timedelta(days=10)
        keep = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=later,
            check_out=later + timedelta(days=1),
        )
        target = create_reservation(
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
        check_in_reservation(target, self.user)
        other = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room_b,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
        )
        check_in_reservation(other, self.user)
        companion = Guest.objects.create(tenant=self.tenant, first_name="Companion", last_name="Guest")
        ReservationOccupant.objects.create(
            tenant=self.tenant,
            reservation=target,
            guest=companion,
            is_primary=False,
        )
        folio = Folio.objects.get(reservation=target)
        shift = CashShift.objects.create(
            tenant=self.tenant, hotel=self.prop, opened_by=self.user
        )
        GuestPayment.objects.create(
            tenant=self.tenant,
            folio=folio,
            amount=Decimal("10000"),
            method=GuestPayment.Method.CASH,
            cash_shift=shift,
            received_by=self.user,
        )
        other_charges = Folio.objects.get(reservation=other).charges.count()
        self.assertGreater(other_charges, 0)
        self.room.refresh_from_db()
        room_status = self.room.status
        board = self.client.get(reverse("bookings:board"))
        self.assertContains(board, reverse("bookings:purge", args=[target.pk]))
        self.client.cookies["django_language"] = "ru"
        board_ru = self.client.get(reverse("bookings:board"))
        self.assertContains(board_ru, "Удалить")
        self.assertContains(board_ru, "Бронь будет удалена полностью")
        self.client.cookies["django_language"] = "uz"

        resp = self.client.post(
            reverse("bookings:purge", args=[target.pk]),
            {"next": reverse("bookings:board")},
        )
        self.assertRedirects(resp, reverse("bookings:board"))
        self.assertFalse(Reservation.objects.filter(pk=target.pk).exists())
        self.assertFalse(Folio.objects.filter(reservation_id=target.pk).exists())
        self.assertFalse(GuestPayment.objects.filter(folio_id=folio.pk).exists())
        self.assertTrue(CashShift.objects.filter(pk=shift.pk).exists())
        self.assertTrue(Reservation.objects.filter(pk=keep.pk).exists())
        self.assertTrue(Reservation.objects.filter(pk=other.pk).exists())
        self.assertEqual(Folio.objects.get(reservation=other).charges.count(), other_charges)
        self.assertTrue(Guest.objects.filter(pk=self.guest.pk).exists())
        self.assertTrue(Guest.objects.filter(pk=companion.pk).exists())
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, room_status)
        self.assertTrue(
            ActivityLog.objects.filter(action="reservation.purge", object_id=str(target.pk)).exists()
        )

        TenantMembership.objects.filter(user=self.user, tenant=self.tenant).update(
            role=TenantMembership.Role.RECEPTIONIST
        )
        denied = self.client.post(reverse("bookings:purge", args=[keep.pk]))
        self.assertEqual(denied.status_code, 302)
        self.assertTrue(Reservation.objects.filter(pk=keep.pk).exists())

    def test_purge_keeps_booking_linked_to_a_service_order(self):
        from services.models import ServiceItem, ServiceOrder

        target = create_reservation(
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
        service = ServiceItem.objects.create(
            tenant=self.tenant, name="Laundry", code="laundry", unit_price=Decimal("10000")
        )
        ServiceOrder.objects.create(
            tenant=self.tenant,
            reservation=target,
            service=service,
            quantity=Decimal("1"),
            unit_price=Decimal("10000"),
            amount=Decimal("10000"),
        )
        from bookings.services import purge_reservation

        with self.assertRaises(ValidationError):
            purge_reservation(target, self.user)
        self.client.force_login(self.user)
        denied = self.client.post(reverse("bookings:purge", args=[target.pk]))
        self.assertEqual(denied.status_code, 302)
        self.assertEqual(denied.url, reverse("bookings:detail", args=[target.pk]))
        self.assertTrue(Reservation.objects.filter(pk=target.pk).exists())
        self.assertTrue(ServiceOrder.objects.filter(reservation=target).exists())
        self.assertTrue(ServiceItem.objects.filter(pk=service.pk).exists())

        company = Company.objects.create(tenant=self.tenant, name="ACME")
        invoice = CompanyInvoice.objects.create(
            tenant=self.tenant, company=company, hotel=self.prop, code="INV-KEEP"
        )
        line = CompanyInvoiceLine.objects.create(
            tenant=self.tenant,
            invoice=invoice,
            description="Stay",
            amount=Decimal("10000"),
            source_reservation=target,
        )
        ServiceOrder.objects.filter(reservation=target).delete()
        with self.assertRaises(ValidationError):
            purge_reservation(target, self.user)
        line.refresh_from_db()
        self.assertEqual(line.source_reservation_id, target.pk)
        self.assertTrue(CompanyInvoice.objects.filter(pk=invoice.pk).exists())
