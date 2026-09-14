from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Reservation, ReservationOccupant
from bookings.occupants import (
    MissingOccupantsError,
    occupant_missing_slots,
    sync_reservation_occupants,
)
from bookings.services import (
    MissingGuestDocsError,
    check_in_reservation,
    create_reservation,
)
from core.tests.helpers import setup_tenant_user
from guests.models import Guest, GuestDocument
from properties.active import SESSION_PROPERTY_KEY
from properties.models import Property, PropertySettings, RatePlan, Room, RoomType
from subscriptions.models import Plan


class OccupantStayTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="occ")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        self.prop = Property.objects.create(tenant=self.tenant, name="Occ Hotel")
        PropertySettings.objects.create(
            tenant=self.tenant, property=self.prop, require_id_on_checkin=False
        )
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Std",
            code="std",
            base_price=100000,
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
            price=100000,
        )
        self.guest = Guest.objects.create(
            tenant=self.tenant, first_name="Ali", last_name="Karimov"
        )
        self.companion = Guest.objects.create(
            tenant=self.tenant, first_name="Nodira", last_name="Aliyeva"
        )
        self.today = timezone.localdate()

    def _res(self, **kwargs):
        data = dict(
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
        data.update(kwargs)
        return create_reservation(**data)

    def test_create_stores_primary_occupant(self):
        reservation = self._res()
        occ = reservation.occupants.get()
        self.assertTrue(occ.is_primary)
        self.assertEqual(occ.guest_id, self.guest.pk)
        self.assertEqual(occ.kind, ReservationOccupant.Kind.ADULT)

    def test_create_with_companion_and_child(self):
        reservation = self._res(
            adults=2,
            children=1,
            occupants=[
                {"guest": self.companion, "kind": ReservationOccupant.Kind.ADULT},
                {
                    "first_name": "Sardor",
                    "last_name": "Karimov",
                    "kind": ReservationOccupant.Kind.CHILD,
                    "doc_number": "AA1112222",
                },
            ],
        )
        self.assertEqual(reservation.occupants.count(), 3)
        self.assertEqual(reservation.adults, 2)
        self.assertEqual(reservation.children, 1)
        child = reservation.occupants.get(kind=ReservationOccupant.Kind.CHILD)
        self.assertEqual(child.guest.first_name, "Sardor")
        self.assertTrue(child.guest.documents.filter(number="AA1112222").exists())

    def test_reuse_guest_by_passport(self):
        GuestDocument.objects.create(
            tenant=self.tenant,
            guest=self.companion,
            doc_type=GuestDocument.DocType.PASSPORT,
            number="BB9998888",
        )
        reservation = self._res(
            adults=2,
            occupants=[
                {
                    "first_name": "Wrong",
                    "doc_number": "BB9998888",
                    "kind": ReservationOccupant.Kind.ADULT,
                }
            ],
        )
        extra = reservation.occupants.get(is_primary=False)
        self.assertEqual(extra.guest_id, self.companion.pk)

    def test_check_in_requires_named_companions(self):
        reservation = self._res(adults=2)
        with self.assertRaises(MissingOccupantsError):
            check_in_reservation(reservation, self.user)
        sync_reservation_occupants(
            reservation,
            [{"guest": self.companion, "kind": ReservationOccupant.Kind.ADULT}],
        )
        stay = check_in_reservation(reservation, self.user)
        self.assertIsNotNone(stay.pk)

    def test_check_in_requires_docs_for_every_occupant(self):
        settings = self.prop.settings
        settings.require_id_on_checkin = True
        settings.save(update_fields=["require_id_on_checkin"])
        GuestDocument.objects.create(
            tenant=self.tenant,
            guest=self.guest,
            doc_type=GuestDocument.DocType.PASSPORT,
            number="AA0001111",
        )
        reservation = self._res(
            adults=2,
            occupants=[{"guest": self.companion, "kind": ReservationOccupant.Kind.ADULT}],
        )
        with self.assertRaises(MissingGuestDocsError):
            check_in_reservation(reservation, self.user)
        check_in_reservation(reservation, self.user, allow_no_docs=True)

    def test_blacklisted_companion_blocked(self):
        self.companion.is_blacklisted = True
        self.companion.blacklist_reason = "fraud"
        self.companion.save(update_fields=["is_blacklisted", "blacklist_reason"])
        with self.assertRaises(ValidationError):
            self._res(
                adults=2,
                occupants=[
                    {"guest": self.companion, "kind": ReservationOccupant.Kind.ADULT}
                ],
            )

    def test_create_view_saves_companion_fields(self):
        url = reverse("bookings:create")
        session = self.client.session
        session[SESSION_PROPERTY_KEY] = self.prop.pk
        session.save()
        payload = {
            "guest": str(self.guest.pk),
            "room_type": str(self.rt.pk),
            "room": str(self.room.pk),
            "nightly_rate": "120000",
            "currency": "USD",
            "check_in": self.today.isoformat(),
            "check_out": (self.today + timedelta(days=1)).isoformat(),
            "adults": "2",
            "children": "0",
            "source": Reservation.Source.PHONE,
            "status": Reservation.Status.CONFIRMED,
            "occ-TOTAL_FORMS": "6",
            "occ-INITIAL_FORMS": "0",
            "occ-MIN_NUM_FORMS": "0",
            "occ-MAX_NUM_FORMS": "8",
            "occ-0-kind": ReservationOccupant.Kind.ADULT,
            "occ-0-first_name": "Malika",
            "occ-0-last_name": "Saidova",
            "occ-0-doc_number": "AA5556666",
            "occ-0-doc_type": GuestDocument.DocType.PASSPORT,
            "occ-0-nationality": "UZ",
            "occ-0-issued_country": "UZ",
        }
        for i in range(1, 6):
            payload[f"occ-{i}-kind"] = ReservationOccupant.Kind.ADULT
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 302)
        reservation = Reservation.objects.get(guest=self.guest)
        self.assertEqual(reservation.occupants.count(), 2)
        extra = reservation.occupants.get(is_primary=False)
        self.assertEqual(extra.guest.first_name, "Malika")
        self.assertTrue(extra.guest.documents.filter(number="AA5556666").exists())

    def _hotel_session(self):
        session = self.client.session
        session[SESSION_PROPERTY_KEY] = self.prop.pk
        session.save()

    def _occ_mgmt(self, extra=None, total=6):
        data = {
            "occ-TOTAL_FORMS": str(total),
            "occ-INITIAL_FORMS": "0",
            "occ-MIN_NUM_FORMS": "0",
            "occ-MAX_NUM_FORMS": "8",
        }
        for i in range(total):
            data[f"occ-{i}-kind"] = ReservationOccupant.Kind.ADULT
        if extra:
            data.update(extra)
        return data

    def test_missing_slots_ignores_already_named_companions(self):
        reservation = self._res(
            adults=3,
            occupants=[{"guest": self.companion, "kind": ReservationOccupant.Kind.ADULT}],
        )
        self.assertEqual(occupant_missing_slots(reservation), (1, 0))

    def test_sync_rejects_primary_as_companion(self):
        reservation = self._res(adults=2)
        with self.assertRaises(ValidationError):
            sync_reservation_occupants(
                reservation,
                [{"guest": self.guest, "kind": ReservationOccupant.Kind.ADULT}],
            )

    def test_create_view_rejects_primary_as_companion(self):
        self._hotel_session()
        payload = {
            "guest": str(self.guest.pk),
            "room_type": str(self.rt.pk),
            "room": str(self.room.pk),
            "nightly_rate": "120000",
            "currency": "USD",
            "check_in": self.today.isoformat(),
            "check_out": (self.today + timedelta(days=1)).isoformat(),
            "adults": "2",
            "children": "0",
            "source": Reservation.Source.PHONE,
            "status": Reservation.Status.CONFIRMED,
            **self._occ_mgmt({"occ-0-guest": str(self.guest.pk)}),
        }
        response = self.client.post(reverse("bookings:create"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Reservation.objects.filter(guest=self.guest).exists())
        self.assertContains(response, "hamroh")

    def test_create_page_derives_companion_cards_from_counts(self):
        self._hotel_session()
        response = self.client.get(reverse("bookings:create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-occupant-root")
        self.assertNotContains(response, "data-extra-adults")
        self.assertContains(response, "Xonadagi mehmonlar")

    def test_check_in_form_asks_only_for_remaining_people(self):
        reservation = self._res(
            adults=3,
            occupants=[{"guest": self.companion, "kind": ReservationOccupant.Kind.ADULT}],
        )
        response = self.client.get(reverse("bookings:detail", args=[reservation.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-extra-adults="1"')
        self.assertNotContains(response, 'data-extra-adults="2"')
        self.assertContains(response, "data-occupant-row", count=1)

    def test_check_in_posts_only_remaining_companion(self):
        reservation = self._res(
            adults=3,
            occupants=[{"guest": self.companion, "kind": ReservationOccupant.Kind.ADULT}],
        )
        payload = self._occ_mgmt(
            {
                "occ-0-first_name": "Sardor",
                "occ-0-last_name": "Karimov",
            },
            total=1,
        )
        response = self.client.post(
            reverse("bookings:check_in", args=[reservation.pk]), payload
        )
        self.assertEqual(response.status_code, 302)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CHECKED_IN)
        self.assertEqual(reservation.occupants.count(), 3)

    def test_walk_in_requires_named_companion(self):
        self._hotel_session()
        response = self.client.post(
            reverse("bookings:walk_in"),
            {
                "first_name": "Walk",
                "room": self.room.pk,
                "nightly_rate": "100000",
                "currency": "USD",
                "nights": 1,
                "adults": 2,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "barcha kishilarning")
        self.assertFalse(Reservation.objects.filter(guest__first_name="Walk").exists())

    def test_walk_in_saves_companion(self):
        self._hotel_session()
        payload = {
            "first_name": "Walk",
            "room": str(self.room.pk),
            "nightly_rate": "100000",
            "currency": "USD",
            "nights": "1",
            "adults": "2",
            **self._occ_mgmt(
                {
                    "occ-0-first_name": "Hamroh",
                    "occ-0-last_name": "Aliyev",
                }
            ),
        }
        response = self.client.post(reverse("bookings:walk_in"), payload)
        self.assertEqual(response.status_code, 302)
        reservation = Reservation.objects.get(guest__first_name="Walk")
        self.assertEqual(reservation.occupants.count(), 2)
        self.assertEqual(
            reservation.occupants.get(is_primary=False).guest.first_name, "Hamroh"
        )

    def test_companion_guest_cannot_be_deleted(self):
        self._res(
            adults=2,
            occupants=[{"guest": self.companion, "kind": ReservationOccupant.Kind.ADULT}],
        )
        response = self.client.post(reverse("guests:delete", args=[self.companion.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Guest.objects.filter(pk=self.companion.pk).exists())
        self.assertEqual(
            response.url, reverse("guests:detail", args=[self.companion.pk])
        )

    def test_reservation_search_matches_companion_name(self):
        self._hotel_session()
        reservation = self._res(
            adults=2,
            occupants=[{"guest": self.companion, "kind": ReservationOccupant.Kind.ADULT}],
        )
        response = self.client.get(reverse("bookings:list"), {"q": "Nodira"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reservation.code)
