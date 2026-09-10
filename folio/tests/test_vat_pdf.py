from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.services import check_in_reservation, create_reservation
from core.tests.helpers import setup_tenant_user
from folio.pdf import build_folio_pdf
from guests.models import Guest
from properties.models import Property, PropertySettings, RatePlan, Room, RoomType
from subscriptions.models import Plan


class VatPdfTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="vatpdf")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        self.prop = Property.objects.create(tenant=self.tenant, name="VAT Hotel")
        PropertySettings.objects.create(
            tenant=self.tenant,
            property=self.prop,
            tax_percent=Decimal("12"),
            require_id_on_checkin=False,
        )
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Std",
            code="std",
            base_price=Decimal("100000"),
        )
        self.room = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="501"
        )
        self.rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="BAR",
            code="bar",
            price=Decimal("100000"),
        )
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Tax")
        self.today = timezone.localdate()

    def test_folio_includes_vat_in_balance(self):
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
        folio = reservation.folio
        from folio.services import ensure_stay_nights_posted

        ensure_stay_nights_posted(reservation, self.user)
        self.assertEqual(folio.charges_total, Decimal("100000"))
        self.assertEqual(folio.tax_amount, Decimal("12000"))
        self.assertEqual(folio.grand_total, Decimal("112000"))
        self.assertEqual(folio.balance, Decimal("112000"))

    def test_pdf_invoice_download(self):
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
        folio = reservation.folio
        pdf_bytes = build_folio_pdf(folio)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        url = reverse("folio:pdf", kwargs={"pk": folio.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
