from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Reservation
from bookings.services import check_in_reservation, create_reservation
from core.tests.helpers import setup_tenant_user
from guests.models import Guest
from housekeeping.services import set_room_status
from properties.models import Property, PropertySettings, RatePlan, Room, RoomType
from reports.models import NightAuditRun
from reports.night_audit import build_cod_checklist, run_night_audit
from subscriptions.models import Plan


class NightAuditCodTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="coduser")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        self.prop = Property.objects.create(tenant=self.tenant, name="COD Hotel")
        PropertySettings.objects.create(
            tenant=self.tenant,
            property=self.prop,
            no_show_fee_percent=Decimal("50"),
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
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="801"
        )
        self.room2 = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="802"
        )
        self.rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="BAR",
            code="bar",
            price=Decimal("100000"),
        )
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Cod")
        self.guest2 = Guest.objects.create(tenant=self.tenant, first_name="Vip", is_vip=True)
        self.today = timezone.localdate()

    def test_auto_no_show_and_day_lock(self):
        missed = create_reservation(
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
        in_house = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest2,
            room_type=self.rt,
            room=self.room2,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
        )
        check_in_reservation(in_house, self.user)
        set_room_status(self.room, Room.Status.DIRTY, user=self.user, note="test")

        preview = build_cod_checklist(self.tenant, self.today)
        self.assertEqual(
            missed.code,
            next(r["code"] for r in preview["missed_arrivals"] if r["pk"] == missed.pk),
        )
        self.assertGreaterEqual(preview["dirty_rooms"], 1)

        run = run_night_audit(self.tenant, self.user, audit_date=self.today, hotel=self.prop)
        self.assertEqual(run.no_shows_marked, 1)
        self.assertGreaterEqual(run.posted_room_charges, 1)
        self.assertGreaterEqual(run.dirty_rooms, 1)
        missed.refresh_from_db()
        self.assertEqual(missed.status, Reservation.Status.NO_SHOW)

        with self.assertRaises(ValidationError) as ctx:
            run_night_audit(self.tenant, self.user, audit_date=self.today, hotel=self.prop)
        self.assertIn("yopilgan", str(ctx.exception).lower())
        self.assertTrue(NightAuditRun.objects.filter(tenant=self.tenant, audit_date=self.today).exists())

    def test_calendar_spans_and_vacant_link(self):
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest2,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=3),
        )
        check_in_reservation(reservation, self.user)
        resp = self.client.get(reverse("bookings:calendar"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'colspan="3"')
        self.assertContains(resp, "status-checked_in")
        self.assertContains(resp, "is-vip")
        self.assertContains(resp, f"room={self.room2.pk}")
        self.assertContains(resp, reverse("bookings:calendar_quick"))
