from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from bookings.services import AvailabilityError, create_reservation
from core.tests.helpers import setup_tenant_user
from guests.models import Guest
from properties.models import Property, RatePlan, Room, RoomType


class FlexRoomSellTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(username="flexroom")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.prop = Property.objects.create(tenant=self.tenant, name="Aida Flex")
        self.twin = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Twin",
            code="twin",
            base_price=Decimal("50"),
            currency="USD",
        )
        self.double = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Double",
            code="double",
            base_price=Decimal("55"),
            currency="USD",
        )
        self.room = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.twin, number="101"
        )
        self.room.sellable_types.set([self.twin, self.double])
        self.rate_twin = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.twin,
            name="BAR Twin",
            code="bar-twin",
            price=Decimal("50"),
            currency="USD",
        )
        self.guest = Guest.objects.create(
            tenant=self.tenant, first_name="Test", last_name="Guest", phone="90001"
        )
        self.today = timezone.localdate()

    def test_sell_as_double_on_twin_primary(self):
        res = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.double,
            room=self.room,
            nightly_rate=Decimal("55"),
            currency="USD",
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
        )
        self.assertEqual(res.room_id, self.room.pk)
        self.assertEqual(res.room_type_id, self.double.pk)

    def test_overlap_blocks_other_config(self):
        create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.twin,
            room=self.room,
            nightly_rate=Decimal("50"),
            currency="USD",
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
        )
        other = Guest.objects.create(
            tenant=self.tenant, first_name="Other", last_name="G", phone="90002"
        )
        with self.assertRaises(AvailabilityError):
            create_reservation(
                tenant=self.tenant,
                user=self.user,
                property_obj=self.prop,
                guest=other,
                room_type=self.double,
                room=self.room,
                nightly_rate=Decimal("55"),
                currency="USD",
                check_in=self.today,
                check_out=self.today + timedelta(days=1),
            )

    def test_config_label(self):
        label = self.room.config_label()
        self.assertIn("Twin", label)
        self.assertIn("Double", label)

    def test_rejects_unsellable_type(self):
        suite = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Suite",
            code="suite",
            base_price=Decimal("100"),
        )
        with self.assertRaises(AvailabilityError):
            create_reservation(
                tenant=self.tenant,
                user=self.user,
                property_obj=self.prop,
                guest=self.guest,
                room_type=suite,
                room=self.room,
                nightly_rate=Decimal("100"),
                check_in=self.today,
                check_out=self.today + timedelta(days=1),
            )

    def test_amend_switches_twin_to_double_same_room(self):
        from bookings.services import apply_amendment

        res = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.twin,
            room=self.room,
            nightly_rate=Decimal("50"),
            currency="USD",
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
        )
        apply_amendment(
            res,
            self.user,
            {
                "check_in": res.check_in,
                "check_out": res.check_out,
                "room": self.room,
                "room_type": self.double,
                "nightly_rate": Decimal("55"),
                "currency": "USD",
                "adults": 2,
                "children": 0,
                "reason": "Double so‘radi",
            },
        )
        res.refresh_from_db()
        self.assertEqual(res.room_id, self.room.pk)
        self.assertEqual(res.room_type_id, self.double.pk)

    def test_transfer_keeps_sold_as_on_flex_room(self):
        from bookings.services import check_in_reservation, transfer_room

        other = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.twin, number="102"
        )
        other.sellable_types.set([self.twin, self.double])
        res = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.double,
            room=self.room,
            nightly_rate=Decimal("55"),
            currency="USD",
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
        )
        check_in_reservation(res, self.user, allow_dirty=True, allow_no_docs=True)
        transfer_room(res, self.user, other, reason="move", update_rate=False)
        res.refresh_from_db()
        self.assertEqual(res.room_id, other.pk)
        self.assertEqual(res.room_type_id, self.double.pk)


class MergeFlexRoomsCommandTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(username="mergeflex")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.prop = Property.objects.create(tenant=self.tenant, name="Merge Hotel")
        self.twin = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Twin",
            code="twin",
            base_price=Decimal("40"),
        )
        self.double = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Double",
            code="double",
            base_price=Decimal("45"),
        )
        self.keeper = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.twin, number="201"
        )
        self.keeper.sellable_types.set([self.twin])
        self.dupe = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.double, number="201-1"
        )
        self.dupe.sellable_types.set([self.double])
        self.guest = Guest.objects.create(
            tenant=self.tenant, first_name="Merge", last_name="Me", phone="91111"
        )
        self.today = timezone.localdate()

    def test_merge_moves_booking_and_adds_type(self):
        res = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.double,
            room=self.dupe,
            nightly_rate=Decimal("45"),
            check_in=self.today + timedelta(days=3),
            check_out=self.today + timedelta(days=5),
        )
        call_command(
            "merge_flex_rooms",
            tenant=str(self.tenant.pk),
            property=str(self.prop.pk),
            apply=True,
        )
        self.dupe.refresh_from_db()
        self.keeper.refresh_from_db()
        res.refresh_from_db()
        self.assertFalse(self.dupe.is_active)
        self.assertEqual(res.room_id, self.keeper.pk)
        self.assertTrue(self.keeper.allows_room_type(self.double))
        self.assertEqual(res.room_type_id, self.double.pk)

    def test_merge_skips_overlap(self):
        create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.twin,
            room=self.keeper,
            nightly_rate=Decimal("40"),
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
        )
        other = Guest.objects.create(
            tenant=self.tenant, first_name="Clash", last_name="X", phone="92222"
        )
        create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=other,
            room_type=self.double,
            room=self.dupe,
            nightly_rate=Decimal("45"),
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
        )
        call_command(
            "merge_flex_rooms",
            tenant=str(self.tenant.pk),
            property=str(self.prop.pk),
            apply=True,
        )
        self.dupe.refresh_from_db()
        self.assertTrue(self.dupe.is_active)
