from django.test import TestCase
from django.urls import reverse

from core.tests.helpers import setup_tenant_user
from guests.models import Guest, GuestDocument
from subscriptions.models import Plan


class GuestEditPassportTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="guestedit")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        self.guest = Guest.objects.create(
            tenant=self.tenant,
            first_name="Ibrahim",
            last_name="Boy",
            nationality="UZ",
        )

    def test_edit_form_shows_passport_fields(self):
        resp = self.client.get(reverse("guests:edit", args=[self.guest.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "doc_number")
        self.assertContains(resp, "Pasport")
        self.assertContains(resp, "name=\"doc_type\"")

    def test_edit_prefills_and_updates_passport(self):
        GuestDocument.objects.create(
            tenant=self.tenant,
            guest=self.guest,
            doc_type=GuestDocument.DocType.PASSPORT,
            number="AA1112222",
            issued_country="UZ",
        )
        resp = self.client.get(reverse("guests:edit", args=[self.guest.pk]))
        self.assertContains(resp, "AA1112222")

        resp = self.client.post(
            reverse("guests:edit", args=[self.guest.pk]),
            {
                "first_name": "Ibrahim",
                "last_name": "Boy",
                "phone": "",
                "email": "",
                "nationality": "UZ",
                "doc_type": GuestDocument.DocType.PASSPORT,
                "doc_number": "AA9998888",
                "issued_country": "UZ",
                "company": "",
                "notes": "",
                "blacklist_reason": "",
            },
        )
        self.assertEqual(resp.status_code, 302)
        doc = self.guest.documents.get()
        self.assertEqual(doc.number, "AA9998888")
        self.assertEqual(self.guest.documents.count(), 1)

    def test_create_saves_passport(self):
        resp = self.client.post(
            reverse("guests:create"),
            {
                "first_name": "Nodira",
                "last_name": "Aliyeva",
                "phone": "",
                "email": "",
                "nationality": "UZ",
                "doc_type": GuestDocument.DocType.ID_CARD,
                "doc_number": "ID1234567",
                "issued_country": "UZ",
                "company": "",
                "notes": "",
                "blacklist_reason": "",
            },
        )
        self.assertEqual(resp.status_code, 302)
        guest = Guest.objects.get(first_name="Nodira")
        doc = guest.documents.get()
        self.assertEqual(doc.number, "ID1234567")
        self.assertEqual(doc.doc_type, GuestDocument.DocType.ID_CARD)
