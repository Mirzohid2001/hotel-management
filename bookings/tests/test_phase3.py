"""Phase 3 — taqvim tez bron, checkout chek, seed demo."""

from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Reservation
from core.tests.helpers import make_property_stack, setup_tenant_user
from finance.models import Expense
from folio.models import GuestPayment
from folio.services import add_payment, ensure_stay_nights_posted, open_cash_shift
from guests.models import Guest
from housekeeping.models import HousekeepingTask
from properties.models import Room
from subscriptions.models import Plan
from tenants.models import Tenant, TenantMembership


class CalendarQuickBookTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="calqb")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        stack = make_property_stack(self.tenant, room_number="301")
        self.prop = stack["property"]
        self.room = stack["room"]
        self.rt = stack["room_type"]
        self.rate = stack["rate_plan"]
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Cal", last_name="Guest")
        self.today = timezone.localdate()

    def test_calendar_page_has_quick_book_trigger(self):
        resp = self.client.get(reverse("bookings:calendar"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse("bookings:calendar_quick"))
        self.assertContains(resp, 'class="cal-new"')

    def test_calendar_quick_modal_get(self):
        url = reverse("bookings:calendar_quick")
        resp = self.client.get(
            f"{url}?room={self.room.pk}&check_in={self.today}&check_out={self.today + timedelta(days=2)}"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Tez bron")
        self.assertContains(resp, self.room.number)

    def test_calendar_quick_book_htmx_creates_reservation(self):
        url = reverse("bookings:calendar_quick")
        check_out = self.today + timedelta(days=2)
        resp = self.client.post(
            url,
            {
                "room": self.room.pk,
                "check_in": self.today.isoformat(),
                "check_out": check_out.isoformat(),
                "guest": self.guest.pk,
                "nightly_rate": "100000",
                "currency": "UZS",
                "adults": 2,
                "status": Reservation.Status.CONFIRMED,
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("calendarRefresh", resp["HX-Trigger"])
        self.assertTrue(
            Reservation.objects.filter(
                tenant=self.tenant, room=self.room, guest=self.guest
            ).exists()
        )

    def test_calendar_htmx_nav_returns_partial(self):
        resp = self.client.get(
            reverse("bookings:calendar"),
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET="calendar-page",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="calendar-page"')
        self.assertNotContains(resp, 'id="spa-root"')

    def test_calendar_boosted_nav_returns_full_page(self):
        resp = self.client.get(
            reverse("bookings:calendar"),
            HTTP_HX_REQUEST="true",
            HTTP_HX_BOOSTED="true",
            HTTP_HX_TARGET="spa-root",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="spa-root"')
        self.assertContains(resp, 'id="calendar-page"')

    def test_calendar_month_view(self):
        from calendar import monthrange

        resp = self.client.get(reverse("bookings:calendar"), {"view": "month"})
        self.assertEqual(resp.status_code, 200)
        days_in_month = monthrange(self.today.year, self.today.month)[1]
        self.assertEqual(resp.context["cal_view"], "month")
        self.assertEqual(resp.context["days_count"], days_in_month)
        self.assertEqual(len(resp.context["days"]), days_in_month)
        self.assertEqual(resp.context["start"].day, 1)
        self.assertContains(resp, "view=month")
        self.assertContains(resp, "1 oy")
        self.assertContains(resp, "14 kun")

    def test_calendar_month_nav_steps_by_month(self):
        resp = self.client.get(
            reverse("bookings:calendar"),
            {"view": "month", "start": "2026-09-15"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["start"].isoformat(), "2026-09-01")
        self.assertEqual(resp.context["prev"].isoformat(), "2026-08-01")
        self.assertEqual(resp.context["next"].isoformat(), "2026-10-01")
        self.assertEqual(resp.context["days_count"], 30)


class CheckoutReceiptTests(TestCase):
    def setUp(self):
        from bookings.services import check_in_reservation, create_reservation

        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="rcpt3")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        stack = make_property_stack(self.tenant, room_number="302")
        self.prop = stack["property"]
        self.room = stack["room"]
        self.rt = stack["room_type"]
        self.rate = stack["rate_plan"]
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Rcpt")
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
        folio = self.reservation.folio
        add_payment(
            folio,
            self.user,
            amount=folio.balance,
            method=GuestPayment.Method.CARD,
        )

    def test_receipt_shows_payments_and_branding(self):
        folio = self.reservation.folio
        resp = self.client.get(reverse("folio:receipt", args=[folio.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.prop.name)
        self.assertContains(resp, "To‘lovlar")
        self.assertContains(resp, "Chop etish")

    def test_pdf_includes_payment_lines(self):
        from folio.pdf import build_folio_pdf

        folio = self.reservation.folio
        pdf = build_folio_pdf(folio)
        self.assertGreater(len(pdf), 500)
        resp = self.client.get(reverse("folio:pdf", args=[folio.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")


class SeedDemoTests(TestCase):
    def test_seed_demo_command(self):
        call_command("seed_demo")
        self.assertTrue(Tenant.objects.filter(slug="rivoj-hotel").exists())
        self.assertTrue(
            TenantMembership.objects.filter(
                user__username="manager", role=TenantMembership.Role.MANAGER
            ).exists()
        )
        tenant = Tenant.objects.get(slug="rivoj-hotel")
        self.assertGreaterEqual(Expense.objects.filter(tenant=tenant).count(), 2)
        self.assertTrue(
            Reservation.objects.filter(tenant=tenant, room__number="102").exists()
        )
        self.assertTrue(
            Room.objects.filter(tenant=tenant, number="201", status=Room.Status.DIRTY).exists()
        )
        self.assertTrue(
            HousekeepingTask.objects.filter(tenant=tenant, room__number="201").exists()
        )
