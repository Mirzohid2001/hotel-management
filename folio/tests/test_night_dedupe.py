from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from django.utils import translation

from bookings.commission import reservation_commission_amount, reservation_commission_base
from bookings.services import check_in_reservation, create_reservation
from core.tests.helpers import setup_tenant_user
from folio.models import Folio, FolioCharge
from folio.services import (
    ensure_stay_nights_posted,
    find_duplicate_night_charges,
    folio_has_night_for_day,
    night_charge_description,
    sum_room_charges_deduped,
    void_duplicate_night_charges,
)
from guests.models import Guest
from properties.models import Property, PropertySettings, RatePlan, Room, RoomType
from reports.services import adr_revpar
from subscriptions.models import Plan


class NightChargeIdempotencyTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="nightdup")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.prop = Property.objects.create(tenant=self.tenant, name="Dup Hotel")
        PropertySettings.objects.create(
            tenant=self.tenant,
            property=self.prop,
            require_id_on_checkin=False,
            emehmon_fee=Decimal("0"),
        )
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Std",
            code="std",
            base_price=Decimal("1000000"),
        )
        self.room = Room.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            number="201",
        )
        self.rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="BAR",
            code="bar",
            price=Decimal("1000000"),
        )
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="2", last_name="2")
        self.today = timezone.localdate()

    def _res(self):
        return create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
            nightly_rate=Decimal("1000000"),
        )

    def test_locale_switch_does_not_post_second_night(self):
        reservation = self._res()
        check_in_reservation(reservation, self.user)
        folio = reservation.folio
        self.assertEqual(
            folio.charges.filter(description__startswith="Night ").count(), 1
        )
        with translation.override("ru"):
            posted = ensure_stay_nights_posted(reservation, self.user)
        self.assertEqual(posted, 0)
        self.assertTrue(folio_has_night_for_day(folio, self.today))
        self.assertEqual(
            folio.charges.filter(description__startswith="Night ", is_void=False).count(),
            1,
        )

    def test_void_duplicates_and_commission_cap(self):
        from bookings.models import BookingReferrer

        ref = BookingReferrer.objects.create(
            tenant=self.tenant,
            name="Abdullo",
            default_commission_percent=Decimal("10"),
        )
        reservation = self._res()
        reservation.referrer = ref
        reservation.commission_percent = Decimal("10")
        reservation.save(update_fields=["referrer", "commission_percent", "updated_at"])
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
        self.assertEqual(reservation_commission_base(reservation), Decimal("1000000"))
        self.assertEqual(reservation_commission_amount(reservation), Decimal("100000.00"))

        groups = find_duplicate_night_charges(tenant=self.tenant)
        self.assertEqual(len(groups), 1)
        result = void_duplicate_night_charges(tenant=self.tenant, dry_run=False)
        self.assertEqual(len(result["voided"]), 1)
        self.assertEqual(
            folio.charges.filter(description__startswith="Night ", is_void=False).count(),
            1,
        )
        # ADR ham dedupe
        stats = adr_revpar(self.tenant, self.today, hotel=self.prop)
        self.assertEqual(stats["room_revenue"], Decimal("1000000"))

    def test_sum_room_charges_deduped_helper(self):
        reservation = self._res()
        folio = Folio.objects.create(tenant=self.tenant, reservation=reservation)
        day = self.today.isoformat()
        a = FolioCharge.objects.create(
            tenant=self.tenant,
            folio=folio,
            charge_type=FolioCharge.ChargeType.ROOM,
            description=f"Night {day} — a",
            quantity=Decimal("1"),
            unit_price=Decimal("1000000"),
            posted_by=self.user,
        )
        FolioCharge.objects.create(
            tenant=self.tenant,
            folio=folio,
            charge_type=FolioCharge.ChargeType.ROOM,
            description=f"Night {day} — b",
            quantity=Decimal("1"),
            unit_price=Decimal("1000000"),
            posted_by=self.user,
        )
        FolioCharge.objects.create(
            tenant=self.tenant,
            folio=folio,
            charge_type=FolioCharge.ChargeType.MINIBAR,
            description="Cola",
            quantity=Decimal("1"),
            unit_price=Decimal("20000"),
            posted_by=self.user,
        )
        total = sum_room_charges_deduped(folio.charges.filter(is_void=False))
        self.assertEqual(total, Decimal("1020000"))
        self.assertEqual(a.amount, Decimal("1000000"))
