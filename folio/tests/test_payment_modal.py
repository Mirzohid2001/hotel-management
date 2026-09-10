"""Sprint 2 — folio to‘lov modali (view/service)."""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.services import check_in_reservation, create_reservation
from core.tests.helpers import make_property_stack, setup_tenant_user
from folio.models import GuestPayment
from folio.services import ensure_stay_nights_posted
from guests.models import Guest
from subscriptions.models import Plan


class FolioPaymentModalTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="foliomod")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        stack = make_property_stack(self.tenant, room_number="401")
        self.prop = stack["property"]
        self.room = stack["room"]
        self.rt = stack["room_type"]
        self.rate = stack["rate_plan"]
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Modal")
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
            check_out=self.today + timedelta(days=1),
        )
        check_in_reservation(self.reservation, self.user)
        ensure_stay_nights_posted(self.reservation, self.user)

    def test_payment_modal_shows_balance(self):
        folio = self.reservation.folio
        self.assertGreater(folio.balance, 0)
        resp = self.client.get(reverse("folio:payment_modal", args=[self.reservation.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Qoldiq")

    def test_payment_modal_prefills_amount(self):
        resp = self.client.get(reverse("folio:payment_modal", args=[self.reservation.pk]))
        balance = self.reservation.folio.balance
        self.assertContains(resp, f'value="{balance.quantize(Decimal("0.01"))}"')

    def test_payment_modal_invalid_amount_rerenders(self):
        folio = self.reservation.folio
        url = reverse("folio:add_payment", args=[folio.pk])
        resp = self.client.post(
            url,
            {
                "from_modal": "1",
                "method": GuestPayment.Method.CASH,
                "kind": GuestPayment.Kind.PAYMENT,
                "amount": "0",
                "note": "",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "modal-dialog")
