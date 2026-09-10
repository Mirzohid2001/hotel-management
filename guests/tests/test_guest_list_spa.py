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

    def test_delete_guest_without_reservations(self):
        guest = Guest.objects.get(first_name="Ali")
        resp = self.client.post(reverse("guests:delete", args=[guest.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Guest.objects.filter(pk=guest.pk).exists())

    def test_cannot_delete_guest_with_reservation(self):
        from datetime import timedelta
        from decimal import Decimal

        from bookings.services import create_reservation
        from django.utils import timezone
        from properties.models import RatePlan, Room, RoomType

        tenant = self.ctx["tenant"]
        user = self.ctx["user"]
        prop = Property.objects.get(tenant=tenant)
        rt = RoomType.objects.create(
            tenant=tenant, property=prop, name="Std", code="std", base_price=Decimal("100000")
        )
        room = Room.objects.create(
            tenant=tenant, property=prop, room_type=rt, number="101"
        )
        rate = RatePlan.objects.create(
            tenant=tenant,
            property=prop,
            room_type=rt,
            name="BAR",
            code="bar",
            price=Decimal("100000"),
        )
        guest = Guest.objects.get(first_name="Ali")
        today = timezone.localdate()
        create_reservation(
            tenant=tenant,
            user=user,
            property_obj=prop,
            guest=guest,
            room_type=rt,
            room=room,
            rate_plan=rate,
            check_in=today,
            check_out=today + timedelta(days=1),
        )
        resp = self.client.post(reverse("guests:delete", args=[guest.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Guest.objects.filter(pk=guest.pk).exists())
