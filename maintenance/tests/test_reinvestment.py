from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.services import check_in_reservation, create_reservation
from core.tests.helpers import setup_tenant_user
from finance.models import Expense, ExpenseCategory, ProfitPartner
from finance.profit import build_partner_ledger
from folio.models import GuestPayment
from folio.services import ensure_folio_for_reservation
from guests.models import Guest
from maintenance.models import MaintenanceTicket
from maintenance.services import (
    cancel_ticket,
    complete_ticket,
    open_ticket,
    record_maintenance_spend,
)
from properties.active import SESSION_PROPERTY_KEY
from properties.models import Property, PropertySettings, RatePlan, Room, RoomType
from reports.accounting import build_pnl_report, cash_pnl_for_range, expenses_in_range
from subscriptions.models import Plan


class MaintenanceReinvestmentTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="maint")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        self.prop = Property.objects.create(tenant=self.tenant, name="Maint Hotel")
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
            base_price=Decimal("100000"),
        )
        self.room = Room.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            number="201",
            status=Room.Status.READY,
        )
        self.rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="BAR",
            code="bar",
            price=Decimal("100000"),
        )
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="G")
        self.today = timezone.localdate()
        session = self.client.session
        session[SESSION_PROPERTY_KEY] = self.prop.pk
        session.save()

    def _revenue(self, amount=Decimal("1000000")):
        res = create_reservation(
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
        check_in_reservation(res, self.user)
        folio = ensure_folio_for_reservation(res)
        GuestPayment.objects.create(
            tenant=self.tenant,
            folio=folio,
            amount=amount,
            method=GuestPayment.Method.CARD,
            kind=GuestPayment.Kind.PAYMENT,
            received_by=self.user,
        )
        return res

    def test_operating_spend_reduces_sof_reinvestment_does_not(self):
        self._revenue()
        record_maintenance_spend(
            self.tenant,
            self.user,
            hotel=self.prop,
            title="Lampochka",
            amount=Decimal("50000"),
            expense_date=self.today,
            funding=Expense.Funding.OPERATING,
        )
        record_maintenance_spend(
            self.tenant,
            self.user,
            hotel=self.prop,
            title="Yangi konditsioner",
            amount=Decimal("300000"),
            expense_date=self.today,
            funding=Expense.Funding.REINVESTMENT,
        )
        # Sof = 1_000_000 - 50_000 (reinvest emas)
        self.assertEqual(
            expenses_in_range(self.tenant, self.today, self.today),
            Decimal("50000"),
        )
        pnl = cash_pnl_for_range(self.tenant, self.today, self.today)
        self.assertEqual(pnl["expenses_total"], Decimal("50000"))
        self.assertEqual(pnl["net"], Decimal("950000"))

        report = build_pnl_report(
            self.tenant, self.today.year, self.today.month, basis="cash"
        )
        self.assertEqual(report["expenses_total"], Decimal("50000"))
        self.assertEqual(report["net"], Decimal("950000"))

    def test_reinvestment_reduces_partner_distributable_only(self):
        self._revenue()
        ProfitPartner.objects.create(
            tenant=self.tenant, name="Boss", share_percent=Decimal("100")
        )
        record_maintenance_spend(
            self.tenant,
            self.user,
            hotel=self.prop,
            title="Katta remont",
            amount=Decimal("200000"),
            expense_date=self.today,
            funding=Expense.Funding.REINVESTMENT,
        )
        ledger = build_partner_ledger(self.tenant)
        self.assertEqual(ledger["operating_net"], Decimal("1000000.00"))
        self.assertEqual(ledger["reinvestment"], Decimal("200000.00"))
        self.assertEqual(ledger["net"], Decimal("800000.00"))
        self.assertEqual(ledger["rows"][0]["entitled"], Decimal("800000.00"))

        # P&L Sof o‘zgarmagan
        pnl = cash_pnl_for_range(self.tenant, self.today, self.today)
        self.assertEqual(pnl["net"], Decimal("1000000"))

    def test_cancel_ticket_and_ooo(self):
        ticket = MaintenanceTicket.objects.create(
            tenant=self.tenant,
            room=self.room,
            title="Kran",
            set_room_ooo=True,
            created_by=self.user,
        )
        open_ticket(ticket)
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, Room.Status.OUT_OF_ORDER)
        cancel_ticket(ticket, user=self.user)
        ticket.refresh_from_db()
        self.room.refresh_from_db()
        self.assertEqual(ticket.status, MaintenanceTicket.Status.CANCELLED)
        self.assertEqual(self.room.status, Room.Status.DIRTY)

    def test_complete_after_cancel_fails(self):
        ticket = MaintenanceTicket.objects.create(
            tenant=self.tenant, room=self.room, title="X", created_by=self.user
        )
        open_ticket(ticket)
        cancel_ticket(ticket, user=self.user)
        with self.assertRaises(Exception):
            complete_ticket(ticket, user=self.user)

    def test_spend_linked_to_ticket_via_ui(self):
        ticket = MaintenanceTicket.objects.create(
            tenant=self.tenant, room=self.room, title="TV", created_by=self.user
        )
        open_ticket(ticket)
        url = reverse("maintenance:spend_create")
        resp = self.client.post(
            url,
            {
                "title": "TV almashtirish",
                "amount": "1500000",
                "currency": "UZS",
                "expense_date": self.today.isoformat(),
                "funding": Expense.Funding.REINVESTMENT,
                "payment_method": Expense.PaymentMethod.TRANSFER,
                "ticket": ticket.pk,
                "notes": "Samsung",
            },
        )
        self.assertEqual(resp.status_code, 302)
        exp = Expense.objects.get(title="TV almashtirish")
        self.assertEqual(exp.funding, Expense.Funding.REINVESTMENT)
        self.assertEqual(exp.status, Expense.Status.PAID)
        self.assertEqual(exp.maintenance_ticket_id, ticket.pk)
        self.assertEqual(exp.category.name, "Reinvestitsiya")

    def test_list_tabs_render(self):
        resp = self.client.get(reverse("maintenance:list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Arizalar")
        resp2 = self.client.get(reverse("maintenance:list") + "?tab=costs")
        self.assertEqual(resp2.status_code, 200)
        self.assertContains(resp2, "Reinvestitsiya")

    def test_cancel_via_post(self):
        ticket = MaintenanceTicket.objects.create(
            tenant=self.tenant, room=self.room, title="Bekor", created_by=self.user
        )
        open_ticket(ticket)
        resp = self.client.post(reverse("maintenance:cancel", args=[ticket.pk]))
        self.assertEqual(resp.status_code, 302)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, MaintenanceTicket.Status.CANCELLED)

    def test_void_removes_from_sof_and_distributable(self):
        self._revenue()
        ProfitPartner.objects.create(
            tenant=self.tenant, name="Boss", share_percent=Decimal("100")
        )
        exp = record_maintenance_spend(
            self.tenant,
            self.user,
            hotel=self.prop,
            title="Xato reinvest",
            amount=Decimal("200000"),
            expense_date=self.today,
            funding=Expense.Funding.REINVESTMENT,
        )
        ledger = build_partner_ledger(self.tenant)
        self.assertEqual(ledger["reinvestment"], Decimal("200000.00"))
        from maintenance.services import void_maintenance_spend

        void_maintenance_spend(exp, self.user, reason="xato")
        ledger2 = build_partner_ledger(self.tenant)
        self.assertEqual(ledger2["reinvestment"], Decimal("0.00"))
        self.assertEqual(ledger2["net"], Decimal("1000000.00"))
        exp.refresh_from_db()
        self.assertEqual(exp.status, Expense.Status.REJECTED)

    def test_reinvestment_appears_in_payment_method_out(self):
        from reports.accounting import payment_method_breakdown

        record_maintenance_spend(
            self.tenant,
            self.user,
            hotel=self.prop,
            title="AC",
            amount=Decimal("100000"),
            expense_date=self.today,
            funding=Expense.Funding.REINVESTMENT,
            payment_method=Expense.PaymentMethod.CASH,
        )
        breakdown = payment_method_breakdown(self.tenant, self.today, self.today)
        cash = next(r for r in breakdown["rows"] if r["method"] == "cash")
        self.assertGreaterEqual(cash["out"], Decimal("100000"))
        # Sofga tegmasin
        pnl = cash_pnl_for_range(self.tenant, self.today, self.today)
        self.assertEqual(pnl["expenses_total"], Decimal("0"))

    def test_ticket_delete_and_spend_edit(self):
        ticket = MaintenanceTicket.objects.create(
            tenant=self.tenant, room=self.room, title="Del", created_by=self.user
        )
        open_ticket(ticket)
        resp = self.client.post(reverse("maintenance:delete", args=[ticket.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(MaintenanceTicket.objects.filter(pk=ticket.pk).exists())

        exp = record_maintenance_spend(
            self.tenant,
            self.user,
            hotel=self.prop,
            title="Old",
            amount=Decimal("50000"),
            expense_date=self.today,
            funding=Expense.Funding.OPERATING,
        )
        resp = self.client.post(
            reverse("maintenance:spend_edit", args=[exp.pk]),
            {
                "title": "New title",
                "amount": "75000",
                "currency": "UZS",
                "expense_date": self.today.isoformat(),
                "funding": Expense.Funding.REINVESTMENT,
                "payment_method": Expense.PaymentMethod.CASH,
                "notes": "",
            },
        )
        self.assertEqual(resp.status_code, 302)
        exp.refresh_from_db()
        self.assertEqual(exp.title, "New title")
        self.assertEqual(exp.amount, Decimal("75000"))
        self.assertEqual(exp.funding, Expense.Funding.REINVESTMENT)
        # Sofdan chiqdi
        self.assertEqual(
            expenses_in_range(self.tenant, self.today, self.today), Decimal("0")
        )
