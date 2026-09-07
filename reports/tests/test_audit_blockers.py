from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.services import check_in_reservation, create_reservation
from core.tests.helpers import setup_tenant_user
from folio.services import add_charge, ensure_folio_for_reservation
from folio.models import FolioCharge
from guests.models import Guest
from properties.models import Property, RatePlan, Room, RoomType
from reports.night_audit import assert_audit_ready, audit_blockers, run_night_audit
from subscriptions.models import Plan


class AuditBlockerTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="blockuser")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.prop = Property.objects.create(tenant=self.tenant, name="Block Hotel")
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Std",
            code="std",
            base_price=Decimal("100000"),
        )
        self.room = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="901"
        )
        self.rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="BAR",
            code="bar",
            price=Decimal("100000"),
        )
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Debt")
        self.today = timezone.localdate()

    def test_overdue_folio_blocks_night_audit(self):
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today - timedelta(days=2),
            check_out=self.today - timedelta(days=1),
        )
        check_in_reservation(reservation, self.user)
        folio = ensure_folio_for_reservation(reservation)
        add_charge(
            folio,
            self.user,
            charge_type=FolioCharge.ChargeType.ROOM,
            description="test",
            unit_price=Decimal("50000"),
            quantity=Decimal("1"),
        )
        reservation.status = reservation.Status.CHECKED_OUT
        reservation.save(update_fields=["status"])

        blockers = audit_blockers(self.tenant, self.today)
        self.assertTrue(blockers)
        with self.assertRaises(ValidationError):
            assert_audit_ready(self.tenant, self.today)
        with self.assertRaises(ValidationError):
            run_night_audit(self.tenant, self.user, audit_date=self.today, hotel=self.prop)

    def test_still_in_house_past_checkout_blocks_audit(self):
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
        blockers = audit_blockers(self.tenant, self.today)
        keys = [b["key"] for b in blockers]
        self.assertIn("still_in_house", keys)
        with self.assertRaises(ValidationError):
            run_night_audit(self.tenant, self.user, audit_date=self.today, hotel=self.prop)

    def test_clean_hotel_passes_audit_blockers(self):
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
        self.assertEqual(audit_blockers(self.tenant, self.today), [])


class AuditBlockerUiTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="blockui")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        self.prop = Property.objects.create(tenant=self.tenant, name="UI Hotel")
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Std",
            code="std",
            base_price=Decimal("100000"),
        )
        self.room = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="902"
        )
        self.rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="BAR",
            code="bar",
            price=Decimal("100000"),
        )
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="UI")
        self.today = timezone.localdate()

    def test_dashboard_shows_blocked_state(self):
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
        resp = self.client.get(reverse("reports:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Kun yopish bloklangan")
        self.assertContains(resp, "Avval muammolarni hal qiling")

    def test_night_audit_post_rejected_when_blocked(self):
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
        resp = self.client.post(reverse("reports:night_audit"))
        self.assertEqual(resp.status_code, 302)
        follow = self.client.get(reverse("reports:dashboard"))
        self.assertContains(follow, "bloklangan", status_code=200)

