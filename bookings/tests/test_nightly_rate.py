"""Qo‘lda kecha narxi — bron, folio, komissiya zanjiri."""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.commission import reservation_commission_amount, reservation_commission_base
from bookings.forms import ReservationForm, WalkInForm
from bookings.models import BookingReferrer, Reservation
from bookings.services import (
    apply_amendment,
    check_in_reservation,
    create_group_booking,
    create_reservation,
    recompute_total,
    transfer_room,
)
from core.tests.helpers import make_property_stack, setup_tenant_user
from folio.models import FolioCharge
from folio.services import ensure_stay_nights_posted, night_amount_for
from guests.models import Guest
from properties.active import SESSION_PROPERTY_KEY
from properties.models import Room, RoomType
from properties.room_type_presets import STANDARD_ROOM_TYPE_CODES
from properties.services import prune_to_standard_room_types
from subscriptions.models import Plan


class ManualNightlyRateChainTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="nightlychk")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        stack = make_property_stack(self.tenant, room_number="801", base_price=Decimal("200000"))
        self.prop = stack["property"]
        self.room = stack["room"]
        self.rt = stack["room_type"]
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Narx", last_name="Test")
        self.today = timezone.localdate()

    def test_total_and_folio_use_nightly_rate(self):
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            nightly_rate=Decimal("275000"),
            check_in=self.today,
            check_out=self.today + timedelta(days=3),
            adults=2,
        )
        self.assertEqual(reservation.total_amount, Decimal("825000"))
        self.assertIsNone(reservation.rate_plan_id)
        self.assertEqual(night_amount_for(reservation, self.today), Decimal("275000"))

        check_in_reservation(reservation, self.user)
        ensure_stay_nights_posted(reservation, self.user)
        charges = list(
            reservation.folio.charges.filter(
                charge_type=FolioCharge.ChargeType.ROOM, is_void=False
            )
        )
        self.assertEqual(len(charges), 3)
        self.assertTrue(all(c.unit_price == Decimal("275000") for c in charges))

    def test_commission_uses_posted_room_charges(self):
        referrer = BookingReferrer.objects.create(
            tenant=self.tenant,
            name="Agent",
            default_commission_percent=Decimal("10"),
        )
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            nightly_rate=Decimal("100000"),
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
            referrer=referrer,
            commission_percent=Decimal("10"),
        )
        check_in_reservation(reservation, self.user)
        ensure_stay_nights_posted(reservation, self.user)
        self.assertEqual(reservation_commission_base(reservation), Decimal("200000"))
        self.assertEqual(reservation_commission_amount(reservation), Decimal("20000"))

    def test_amend_replaces_rate_plan_with_nightly(self):
        rate = make_property_stack(
            self.tenant, name="Amend Hotel", room_number="802", base_price=Decimal("150000")
        )
        room2 = rate["room"]
        guest2 = Guest.objects.create(tenant=self.tenant, first_name="Amend")
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=rate["property"],
            guest=guest2,
            room_type=rate["room_type"],
            room=room2,
            rate_plan=rate["rate_plan"],
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
        )
        self.assertIsNotNone(reservation.rate_plan_id)
        apply_amendment(
            reservation,
            self.user,
            {
                "check_in": self.today,
                "check_out": self.today + timedelta(days=2),
                "room": room2,
                "nightly_rate": Decimal("180000"),
                "adults": 1,
                "children": 0,
                "reason": "manual price",
            },
        )
        reservation.refresh_from_db()
        self.assertEqual(reservation.nightly_rate, Decimal("180000"))
        self.assertIsNone(reservation.rate_plan_id)
        self.assertEqual(reservation.total_amount, Decimal("360000"))

    def test_transfer_keeps_manual_nightly(self):
        twin = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Twin · Ikki alohida",
            code="twin",
            base_price=Decimal("220000"),
        )
        twin_room = Room.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=twin,
            number="803",
        )
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            nightly_rate=Decimal("199000"),
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
        )
        check_in_reservation(reservation, self.user)
        transfer_room(reservation, self.user, twin_room, update_rate=True)
        reservation.refresh_from_db()
        self.assertEqual(reservation.room_id, twin_room.pk)
        self.assertEqual(reservation.nightly_rate, Decimal("199000"))
        self.assertIsNone(reservation.rate_plan_id)
        self.assertEqual(recompute_total(reservation), Decimal("398000"))

    def test_group_booking_nightly_rates(self):
        room2 = Room.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            number="804",
        )
        guest2 = Guest.objects.create(tenant=self.tenant, first_name="G2")
        group, created = create_group_booking(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            name="Group N",
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
            rooms_data=[
                {
                    "guest": self.guest,
                    "room_type": self.rt,
                    "room": self.room,
                    "nightly_rate": Decimal("111000"),
                },
                {
                    "guest": guest2,
                    "room_type": self.rt,
                    "room": room2,
                    "nightly_rate": Decimal("222000"),
                },
            ],
        )
        self.assertEqual(len(created), 2)
        amounts = sorted(r.total_amount for r in group.reservations.all())
        self.assertEqual(amounts, [Decimal("222000"), Decimal("444000")])

    def test_reservation_form_rejects_missing_nightly(self):
        form = ReservationForm(
            {
                "guest": self.guest.pk,
                "room_type": self.rt.pk,
                "room": self.room.pk,
                "check_in": self.today.isoformat(),
                "check_out": (self.today + timedelta(days=1)).isoformat(),
                "adults": 1,
                "children": 0,
                "source": Reservation.Source.PHONE,
                "status": Reservation.Status.CONFIRMED,
            },
            tenant=self.tenant,
            hotel=self.prop,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("nightly_rate", form.errors)

    def test_walk_in_form_requires_nightly(self):
        form = WalkInForm(
            {
                "first_name": "W",
                "room": str(self.room.pk),
                "nights": 1,
                "adults": 1,
            },
            tenant=self.tenant,
            hotel=self.prop,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("nightly_rate", form.errors)


class StandardRoomTypePruneTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(username="prunecheck")
        self.tenant = self.ctx["tenant"]
        stack = make_property_stack(self.tenant, room_number="901", base_price=Decimal("100000"))
        self.prop = stack["property"]
        self.room = stack["room"]

    def test_prune_deactivates_extras_and_remaps_rooms(self):
        suite = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Suite · Lyuks",
            code="suite",
            base_price=Decimal("500000"),
        )
        self.room.room_type = suite
        self.room.save(update_fields=["room_type"])
        RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Double · Juftlik",
            code="double",
            base_price=Decimal("100000"),
        )
        result = prune_to_standard_room_types(prop=self.prop)
        self.assertIn("suite", result["deactivated"])
        self.room.refresh_from_db()
        self.assertEqual(self.room.room_type.code, "double")
        active = set(
            RoomType.objects.filter(property=self.prop, is_active=True).values_list(
                "code", flat=True
            )
        )
        self.assertTrue(active.issubset(STANDARD_ROOM_TYPE_CODES))
        self.assertEqual(active, {"twin", "double", "triple"})

    def test_create_page_room_type_choices_only_active(self):
        RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Dead",
            code="suite",
            base_price=Decimal("1"),
            is_active=False,
        )
        twin = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Twin",
            code="twin",
            base_price=Decimal("100000"),
        )
        self.client.force_login(self.ctx["user"])
        session = self.client.session
        session[SESSION_PROPERTY_KEY] = self.prop.pk
        session.save()
        resp = self.client.get(reverse("bookings:create"))
        self.assertEqual(resp.status_code, 200)
        form = resp.context["form"]
        codes = set(form.fields["room_type"].queryset.values_list("code", flat=True))
        self.assertIn(twin.code, codes)
        self.assertNotIn("suite", codes)
