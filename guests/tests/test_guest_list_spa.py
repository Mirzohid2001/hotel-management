from django.test import TestCase
from django.urls import reverse

from core.tests.helpers import setup_tenant_user
from guests.models import Guest
from properties.models import Property
from subscriptions.models import Plan


class GuestListSpaTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.FREE, username="spa_guest")
        self.client.force_login(self.ctx["user"])
        Property.objects.create(tenant=self.ctx["tenant"], name="H1")
        Guest.objects.create(
            tenant=self.ctx["tenant"], first_name="Ali", last_name="Karimov"
        )

    def test_boosted_nav_returns_full_page_with_spa_root(self):
        url = reverse("guests:list")
        resp = self.client.get(
            url,
            HTTP_HX_REQUEST="true",
            HTTP_HX_BOOSTED="true",
            HTTP_HX_TARGET="spa-root",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="spa-root"')
        self.assertContains(resp, "Ali")
        self.assertContains(resp, "Mehmonlar")

    def test_search_partial_returns_results_only(self):
        url = reverse("guests:list")
        resp = self.client.get(
            url,
            {"q": "Ali"},
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET="guest-results",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Ali")
        self.assertContains(resp, "Bron")
        self.assertContains(resp, "Profil")
        self.assertNotContains(resp, 'id="spa-root"')

    def test_flag_filter_vip(self):
        Guest.objects.create(
            tenant=self.ctx["tenant"], first_name="VIP", last_name="Guest", is_vip=True
        )
        resp = self.client.get(reverse("guests:list"), {"flag": "vip"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "VIP Guest")
        self.assertNotContains(resp, "Ali")
