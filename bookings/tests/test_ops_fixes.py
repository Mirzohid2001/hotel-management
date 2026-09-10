from datetime import timedelta
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
    create_reservation,
)
from core.notifications import build_notifications
from core.tests.helpers import make_membership, make_user, setup_tenant_user
from folio.models import FolioCharge
from folio.services import add_payment, ensure_stay_nights_posted
from guests.models import Guest
from housekeeping.models import HousekeepingTask
from properties.models import Property, PropertySettings, RatePlan, Room, RoomType
from reports.night_audit import run_night_audit
from subscriptions.models import Plan
from tenants.models import TenantMembership


class CriticalOpsFixesTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="critfix")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        self.prop = Property.objects.create(tenant=self.tenant, name="Fix Hotel")
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
        self.room = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="701"
        )
        self.rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="BAR",
            code="bar",
            price=Decimal("100000"),
        )
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Crit")
        self.today = timezone.localdate()

    def _reservation(self, nights=2):
        return create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=nights),
        )

    def test_no_double_room_charge_checkin_then_night_audit(self):
        reservation = self._reservation(nights=2)
        check_in_reservation(reservation, self.user)
        folio = reservation.folio
        # Check-in endi barcha kechalarni yozadi; night audit qayta yozmaydi.
        self.assertEqual(
            folio.charges.filter(charge_type=FolioCharge.ChargeType.ROOM).count(), 2
        )
        run = run_night_audit(self.tenant, self.user, audit_date=self.today, hotel=self.prop)
        self.assertEqual(run.posted_room_charges, 0)
        self.assertEqual(
            folio.charges.filter(charge_type=FolioCharge.ChargeType.ROOM).count(), 2
        )
        self.assertEqual(folio.charges_total, Decimal("200000"))
        self.assertEqual(
            folio.charges.filter(description__contains=self.today.isoformat()).count(), 1
        )

    def test_legacy_prepaid_skips_night_audit(self):
        reservation = self._reservation(nights=1)
        check_in_reservation(reservation, self.user)
        folio = reservation.folio
        # Check-in yozgan Night yozuvlarini olib, eski uslubdagi prepaid ROOM qoldiramiz
        folio.charges.filter(charge_type=FolioCharge.ChargeType.ROOM).delete()
        FolioCharge.objects.create(
            tenant=self.tenant,
            folio=folio,
            charge_type=FolioCharge.ChargeType.ROOM,
            description="Room 1 night(s)",
            quantity=Decimal("1"),
            unit_price=Decimal("100000"),
            posted_by=self.user,
        )
        run = run_night_audit(self.tenant, self.user, audit_date=self.today, hotel=self.prop)
        self.assertEqual(run.posted_room_charges, 0)
        self.assertEqual(folio.charges.filter(charge_type="room").count(), 1)

    def test_checkout_blocked_when_unpaid(self):
        reservation = self._reservation(nights=1)
        check_in_reservation(reservation, self.user)
        with self.assertRaises(ValidationError) as ctx:
            check_out_reservation(reservation, self.user)
        self.assertIn("to‘lanmagan qoldiq", str(ctx.exception).lower())
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CHECKED_IN)

    def test_checkout_reopens_closed_folio(self):
        reservation = self._reservation(nights=1)
        check_in_reservation(reservation, self.user)
        folio = reservation.folio
        ensure_stay_nights_posted(reservation, self.user)
        add_payment(folio, self.user, amount=folio.balance, method="card")
        # Noto‘g‘ri yopilgan hisob — chiqish hali mumkin bo‘lishi kerak
        folio.is_open = False
        folio.save(update_fields=["is_open", "updated_at"])
        check_out_reservation(reservation, self.user)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CHECKED_OUT)

    def test_cannot_close_folio_while_checked_in(self):
        from folio.services import close_folio

        reservation = self._reservation(nights=1)
        check_in_reservation(reservation, self.user)
        ensure_stay_nights_posted(reservation, self.user)
        add_payment(reservation.folio, self.user, amount=reservation.folio.balance, method="card")
        with self.assertRaises(ValidationError) as ctx:
            close_folio(reservation.folio)
        self.assertIn("joylashgan", str(ctx.exception).lower())

    def test_alerts_ignore_midstay_balance(self):
        reservation = self._reservation(nights=3)
        check_in_reservation(reservation, self.user)
        ensure_stay_nights_posted(reservation, self.user)
        # still mid-stay (checkout in 3 days), balance > 0
        self.assertGreater(reservation.folio.balance, 0)
        self.assertGreater(reservation.check_out, self.today)
        notes = build_notifications(self.tenant)
        overdue = [i for i in notes["items"] if i["kind"] == "overdue"]
        self.assertEqual(overdue, [])

    def test_alerts_flag_departure_day_debt(self):
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today - timedelta(days=1),
            check_out=self.today,
        )
        check_in_reservation(reservation, self.user)
        ensure_stay_nights_posted(reservation, self.user)
        notes = build_notifications(self.tenant)
        overdue = [i for i in notes["items"] if i["kind"] == "overdue"]
        self.assertTrue(any(i["pk"] == reservation.pk for i in overdue))

    def test_staff_admin_forbidden_for_manager(self):
        mgr = make_user(username="mgrstaff")
        make_membership(mgr, self.tenant, role=TenantMembership.Role.MANAGER)
        self.client.force_login(mgr)
        resp = self.client.get(reverse("tenants:staff_list"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("bookings:board"))
