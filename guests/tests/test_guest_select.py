from django.test import TestCase
from django.urls import reverse

from core.tests.helpers import make_property_stack, setup_tenant_user
from guests.models import Guest
from guests.query import guests_for_select
from properties.active import SESSION_PROPERTY_KEY
from subscriptions.models import Plan


class GuestSelectOrderTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="guestalpha")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        stack = make_property_stack(self.tenant, room_number="101")
        self.prop = stack["property"]
        session = self.client.session
        session[SESSION_PROPERTY_KEY] = self.prop.pk
        session.save()
        Guest.objects.create(tenant=self.tenant, first_name="Zarina", last_name="Aliyeva")
        Guest.objects.create(tenant=self.tenant, first_name="alina", last_name="Bek")
        Guest.objects.create(tenant=self.tenant, first_name="Bekzod", last_name="")

    def test_guests_for_select_alpha_case_insensitive(self):
        names = [g.full_name for g in guests_for_select(self.tenant)]
        self.assertEqual(names, ["alina Bek", "Bekzod", "Zarina Aliyeva"])

    def test_reservation_form_has_searchable_guest(self):
        resp = self.client.get(reverse("bookings:create"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-searchable-select')
        self.assertContains(resp, "searchable-select-query")
        self.assertContains(resp, "Ism bo‘yicha qidirish")
        # Options appear in alpha order in the native select
        body = resp.content.decode()
        i_alina = body.index(">alina Bek<")
        i_bek = body.index(">Bekzod<")
        i_zarina = body.index(">Zarina Aliyeva<")
        self.assertLess(i_alina, i_bek)
        self.assertLess(i_bek, i_zarina)
