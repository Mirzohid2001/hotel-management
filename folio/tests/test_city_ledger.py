from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.services import check_in_reservation, create_reservation
from core.tests.helpers import setup_tenant_user
from folio.city_ledger import (
    add_company_payment,
    ar_aging,
    company_open_balance,
    transfer_open_charges_to_company,
)
from folio.models import CompanyInvoice, FolioCharge, GuestPayment
from folio.services import add_charge, ensure_stay_nights_posted
from guests.models import Company, Guest
from properties.models import Property, PropertySettings, RatePlan, Room, RoomType
from subscriptions.models import Plan


class CityLedgerTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="cityledger")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        self.prop = Property.objects.create(tenant=self.tenant, name="AR Hotel")
        PropertySettings.objects.create(
            tenant=self.tenant,
            property=self.prop,
            tax_percent=Decimal("12"),
            require_id_on_checkin=False,
        )
        self.company = Company.objects.create(
            tenant=self.tenant,
            name="Acme Corp",
            payment_terms_days=30,
            credit_limit=Decimal("5000000"),
        )
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Std",
            code="std",
            base_price=Decimal("100000"),
        )
        self.room = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="901"
        )
        self.rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="BAR",
            code="bar",
            price=Decimal("100000"),
        )
        self.guest = Guest.objects.create(
            tenant=self.tenant, first_name="Corp", company=self.company
        )
        self.today = timezone.localdate()

    def _checked_in(self):
        reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            company=self.company,
            room_type=self.rt,
            room=self.room,
            rate_plan=self.rate,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
        )
        check_in_reservation(reservation, self.user)
        ensure_stay_nights_posted(reservation, self.user)
        return reservation

    def test_transfer_charges_creates_invoice_and_voids(self):
        reservation = self._checked_in()
        folio = reservation.folio
        self.assertGreater(folio.charges_total, 0)
        before_tax = folio.tax_amount
        invoice = transfer_open_charges_to_company(folio, self.user)
        folio.refresh_from_db()
        self.assertEqual(folio.charges.filter(is_void=False).count(), 0)
        self.assertEqual(folio.charges_total, Decimal("0"))
        self.assertEqual(invoice.company_id, self.company.pk)
        # room 100000 + VAT 12% = 112000
        self.assertEqual(invoice.lines_total, Decimal("100000") + before_tax)
        self.assertEqual(invoice.balance, invoice.lines_total)
        self.assertEqual(invoice.status, CompanyInvoice.Status.OPEN)

    def test_company_payment_and_aging(self):
        reservation = self._checked_in()
        invoice = transfer_open_charges_to_company(reservation.folio, self.user)
        pay = add_company_payment(
            invoice,
            self.user,
            amount=invoice.balance,
            method=GuestPayment.Method.TRANSFER,
            note="wire",
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, CompanyInvoice.Status.PAID)
        self.assertEqual(invoice.balance, Decimal("0"))
        self.assertEqual(company_open_balance(self.company), Decimal("0"))
        self.assertFalse(pay.is_void)

        # second open invoice for aging
        add_charge(
            reservation.folio,
            self.user,
            charge_type=FolioCharge.ChargeType.OTHER,
            description="Late fee",
            unit_price=Decimal("20000"),
        )
        inv2 = transfer_open_charges_to_company(reservation.folio, self.user)
        aging = ar_aging(self.tenant)
        self.assertGreater(aging["grand_total"], 0)
        self.assertGreaterEqual(len(aging["buckets"]["current"]["invoices"]), 1)
        self.assertEqual(inv2.status, CompanyInvoice.Status.OPEN)

    def test_credit_limit_blocks_transfer(self):
        self.company.credit_limit = Decimal("1000")
        self.company.save(update_fields=["credit_limit"])
        reservation = self._checked_in()
        with self.assertRaises(ValidationError) as ctx:
            transfer_open_charges_to_company(reservation.folio, self.user)
        self.assertIn("kredit limiti", str(ctx.exception).lower())

    def test_city_ledger_pages(self):
        reservation = self._checked_in()
        invoice = transfer_open_charges_to_company(reservation.folio, self.user)
        list_resp = self.client.get(reverse("folio:city_ledger"))
        self.assertEqual(list_resp.status_code, 200)
        self.assertContains(list_resp, invoice.code)
        detail = self.client.get(reverse("folio:invoice_detail", args=[invoice.pk]))
        self.assertEqual(detail.status_code, 200)
        pdf = self.client.get(reverse("folio:invoice_pdf", args=[invoice.pk]))
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        company_page = self.client.get(reverse("guests:company_detail", args=[self.company.pk]))
        self.assertEqual(company_page.status_code, 200)
        self.assertContains(company_page, invoice.code)
