"""Sprint 2 — doska to‘lov modali va walk-in depozit."""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Reservation
from bookings.services import check_in_reservation, create_reservation
from core.tests.helpers import make_property_stack, setup_tenant_user
from folio.models import GuestPayment
from folio.services import ensure_stay_nights_posted
from guests.models import Guest
from subscriptions.models import Plan


class BoardPaymentModalTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="boardpay")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        stack = make_property_stack(self.tenant, room_number="501")
        self.prop = stack["property"]
        self.room = stack["room"]
        self.rt = stack["room_type"]
        self.rate = stack["rate_plan"]
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Pay")
        self.today = timezone.localdate()
        self.reservation = create_reservation(
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
        check_in_reservation(self.reservation, self.user)
        ensure_stay_nights_posted(self.reservation, self.user)

    def test_board_shows_payment_button_and_balance(self):
        resp = self.client.get(reverse("bookings:board"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse("folio:payment_modal", args=[self.reservation.pk]))
        self.assertContains(resp, "To‘lov")

    def test_payment_modal_get(self):
        url = reverse("folio:payment_modal", args=[self.reservation.pk])
        resp = self.client.get(f"{url}?from=board", HTTP_HX_REQUEST="true")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.reservation.code)
        self.assertContains(resp, "Qabul qilish")
        self.assertContains(resp, 'name="from_modal"')

    def test_payment_modal_post_htmx_triggers_board_refresh(self):
        folio = self.reservation.folio
        amount = folio.balance
        url = reverse("folio:add_payment", args=[folio.pk])
        resp = self.client.post(
            url,
            {
                "from_modal": "1",
                "from_board": "1",
                "method": GuestPayment.Method.CARD,
                "kind": GuestPayment.Kind.PAYMENT,
                "amount": str(amount),
                "currency": "UZS",
                "note": "",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("boardRefresh", resp["HX-Trigger"])
        self.assertIn("modalClosed", resp["HX-Trigger"])
        folio.refresh_from_db()
        self.assertEqual(folio.balance, Decimal("0"))


class WalkInDepositPromptTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="walkdep")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        stack = make_property_stack(self.tenant, room_number="502")
        self.prop = stack["property"]
        self.room = stack["room"]
        self.rt = stack["room_type"]
        self.rate = stack["rate_plan"]
        self.today = timezone.localdate()

    def test_walk_in_redirects_with_deposit_prompt(self):
        resp = self.client.post(
            reverse("bookings:walk_in"),
            {
                "first_name": "Walk",
                "last_name": "Guest",
                "phone": "99890",
                "room": self.room.pk,
                "nightly_rate": "100000",
                "nights": 1,
                "adults": 1,
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("prompt_deposit=1", resp.url)
        reservation = Reservation.objects.get(tenant=self.tenant, guest__first_name="Walk")
        self.assertEqual(reservation.status, Reservation.Status.CHECKED_IN)
        self.assertTrue(hasattr(reservation, "folio"))

    def test_reservation_detail_loads_deposit_modal(self):
        guest = Guest.objects.create(tenant=self.tenant, first_name="Dep")
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
        )
        check_in_reservation(reservation, self.user)
        url = reverse("bookings:detail", args=[reservation.pk])
        resp = self.client.get(f"{url}?prompt_deposit=1")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse("folio:payment_modal", args=[reservation.pk]))
        self.assertContains(resp, "kind=deposit")

    def test_deposit_modal_kind_defaults_to_deposit(self):
        guest = Guest.objects.create(tenant=self.tenant, first_name="Dep2")
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=guest,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
        )
        check_in_reservation(reservation, self.user)
        url = reverse("folio:payment_modal", args=[reservation.pk])
        resp = self.client.get(f"{url}?kind=deposit")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Depozit")
