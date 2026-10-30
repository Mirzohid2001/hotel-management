from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import ReservationOccupant
from bookings.occupants import reservation_guest_display_names
from bookings.services import check_in_reservation, create_reservation
from core.tests.helpers import setup_tenant_user
from folio.pdf import build_folio_pdf
from guests.models import Guest
from properties.models import Property, PropertySettings, RatePlan, Room, RoomType
from subscriptions.models import Plan


class ReceiptOccupantNamesTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="rcptocc")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        self.prop = Property.objects.create(tenant=self.tenant, name="Occ Hotel")
        PropertySettings.objects.create(
            tenant=self.tenant,
            property=self.prop,
            require_id_on_checkin=False,
        )
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Twin",
            code="twin",
            base_price=Decimal("100000"),
        )
        self.room = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="203"
        )
        self.rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="BAR",
            code="bar",
            price=Decimal("100000"),
        )
        self.primary = Guest.objects.create(
            tenant=self.tenant, first_name="Makhdi", last_name="Farashiani"
        )
        self.companion = Guest.objects.create(
            tenant=self.tenant, first_name="Farashyani", last_name="Mohammadreza"
        )
        self.today = timezone.localdate()

    def _folio_with_two_guests(self):
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.primary,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
            adults=2,
            occupants=[
                {"guest": self.companion, "kind": ReservationOccupant.Kind.ADULT},
            ],
        )
        check_in_reservation(reservation, self.user, allow_no_docs=True)
        return reservation.folio

    def test_display_names_include_companions(self):
        folio = self._folio_with_two_guests()
        names = reservation_guest_display_names(folio.reservation)
        self.assertEqual(len(names), 2)
        self.assertIn("Makhdi Farashiani", names)
        self.assertIn("Farashyani Mohammadreza", names)

    def test_receipt_html_lists_both_names(self):
        folio = self._folio_with_two_guests()
        resp = self.client.get(reverse("folio:receipt", args=[folio.pk]))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("Makhdi Farashiani", body)
        self.assertIn("Farashyani Mohammadreza", body)

    def test_pdf_builds_with_companions(self):
        folio = self._folio_with_two_guests()
        self.assertEqual(len(reservation_guest_display_names(folio.reservation)), 2)
        pdf = build_folio_pdf(folio)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 500)
