"""Phase 2 — checkout modali va operatsion audit log."""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.services import check_in_reservation, check_out_reservation, create_reservation
from core.models import ActivityLog
from core.tests.helpers import make_property_stack, setup_tenant_user
from folio.services import add_payment, ensure_stay_nights_posted, open_cash_shift
from folio.models import GuestPayment
from guests.models import Guest
from housekeeping.models import HousekeepingTask
from housekeeping.services import complete_task
from subscriptions.models import Plan


class CheckoutModalTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="chkmod")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        stack = make_property_stack(self.tenant, room_number="801")
        self.prop = stack["property"]
        self.room = stack["room"]
        self.rt = stack["room_type"]
        self.rate = stack["rate_plan"]
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Out")
        self.today = timezone.localdate()
        open_cash_shift(self.tenant, self.user, Decimal("0"), hotel=self.prop)
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

    def test_board_shows_checkout_modal_trigger(self):
        resp = self.client.get(reverse("bookings:board"))
        self.assertContains(resp, reverse("bookings:checkout_modal", args=[self.reservation.pk]))

    def test_checkout_modal_shows_balance(self):
        url = reverse("bookings:checkout_modal", args=[self.reservation.pk])
        resp = self.client.get(f"{url}?from=board")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Qoldiq")
        self.assertGreater(self.reservation.folio.balance, 0)

    def test_checkout_modal_blocks_when_unpaid(self):
        url = reverse("bookings:checkout_modal", args=[self.reservation.pk])
        resp = self.client.get(url)
        self.assertContains(resp, "To‘lov qabul qilish")
        self.assertNotContains(resp, "Chiqishni tasdiqlash")

    def test_checkout_modal_htmx_success(self):
        folio = self.reservation.folio
        add_payment(
            folio,
            self.user,
            amount=folio.balance,
            method=GuestPayment.Method.CARD,
        )
        url = reverse("bookings:check_out", args=[self.reservation.pk])
        resp = self.client.post(
            url,
            {"from_modal": "1", "from_board": "1"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Chiqish bajarildi")
        self.assertContains(resp, reverse("folio:receipt", args=[folio.pk]))
        self.assertContains(resp, reverse("folio:pdf", args=[folio.pk]))
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, self.reservation.Status.CHECKED_OUT)


class OpsActivityLogTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="actops")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        stack = make_property_stack(self.tenant, room_number="802")
        self.prop = stack["property"]
        self.room = stack["room"]
        self.rt = stack["room_type"]
        self.rate = stack["rate_plan"]
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Log")
        self.today = timezone.localdate()

    def test_check_in_logs_activity(self):
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
        self.assertTrue(
            ActivityLog.objects.filter(
                tenant=self.tenant, action="guest_check_in", object_id=str(reservation.pk)
            ).exists()
        )

    def test_check_out_logs_activity(self):
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
        ensure_stay_nights_posted(reservation, self.user)
        add_payment(
            reservation.folio,
            self.user,
            amount=reservation.folio.balance,
            method=GuestPayment.Method.CARD,
        )
        check_out_reservation(reservation, self.user)
        self.assertTrue(
            ActivityLog.objects.filter(
                tenant=self.tenant, action="guest_check_out", object_id=str(reservation.pk)
            ).exists()
        )

    def test_hk_complete_logs_activity(self):
        task = HousekeepingTask.objects.create(
            tenant=self.tenant,
            room=self.room,
            title="Test clean",
        )
        complete_task(task, user=self.user)
        self.assertTrue(
            ActivityLog.objects.filter(tenant=self.tenant, action="hk_task_done").exists()
        )
