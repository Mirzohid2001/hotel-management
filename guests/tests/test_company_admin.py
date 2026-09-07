from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.tests.helpers import setup_tenant_user
from guests.forms import CompanyAdminForm
from guests.models import Company
from subscriptions.models import Plan


class CompanyAdminCreateTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="coadmin")
        self.tenant = self.ctx["tenant"]
        self.user = get_user_model().objects.create_superuser(
            username="platadmin",
            email="plat@example.com",
            password="pass12345",
        )

    def test_admin_form_accepts_empty_numeric_fields(self):
        form = CompanyAdminForm(
            data={
                "tenant": self.tenant.pk,
                "name": "Yangi Korxona",
                "inn": "",
                "phone": "",
                "email": "",
                "address": "",
                "notes": "",
                "is_active": True,
                "payment_terms_days": "",
                "credit_limit": "",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        company = form.save()
        self.assertEqual(company.payment_terms_days, 30)
        self.assertEqual(company.credit_limit, Decimal("0"))

    def test_admin_add_view_saves_with_empty_terms(self):
        self.client.force_login(self.user)
        url = reverse("admin:guests_company_add")
        resp = self.client.post(
            url,
            {
                "name": "Admin Qo‘shilgan",
                "tenant": self.tenant.pk,
                "inn": "900",
                "phone": "",
                "email": "",
                "address": "",
                "notes": "",
                "is_active": "on",
                "payment_terms_days": "",
                "credit_limit": "",
                "_save": "Save",
            },
        )
        self.assertEqual(resp.status_code, 302, getattr(resp, "context", None))
        company = Company.objects.get(tenant=self.tenant, name="Admin Qo‘shilgan")
        self.assertEqual(company.payment_terms_days, 30)
        self.assertEqual(company.credit_limit, Decimal("0"))

    def test_duplicate_name_rejected(self):
        Company.objects.create(tenant=self.tenant, name="Aida")
        form = CompanyAdminForm(
            data={
                "tenant": self.tenant.pk,
                "name": "Aida",
                "inn": "",
                "phone": "",
                "email": "",
                "address": "",
                "notes": "",
                "is_active": True,
                "payment_terms_days": "30",
                "credit_limit": "0",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertTrue(form.errors)
