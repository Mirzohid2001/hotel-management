"""Sprint 3 — HK doskasi va ta’mirlash eskalatsiyasi."""

from django.test import TestCase
from django.urls import reverse

from core.tests.helpers import make_property_stack, setup_tenant_user
from maintenance.models import MaintenanceTicket
from properties.models import Room
from subscriptions.models import Plan


class HkMaintenanceRoadmapTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="hkroad")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client.force_login(self.user)
        stack = make_property_stack(self.tenant, room_number="601")
        self.room = stack["room"]

    def test_hk_board_shows_touch_actions(self):
        resp = self.client.get(reverse("housekeeping:board"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Tayyor")
        self.assertContains(resp, "Tozalash")
        self.assertContains(resp, "Kir")
        self.assertContains(resp, "Nosozlik")

    def test_hk_quick_status_ready(self):
        self.room.status = Room.Status.DIRTY
        self.room.save(update_fields=["status"])
        resp = self.client.post(
            reverse("housekeeping:set_status", args=[self.room.pk]),
            {"status": Room.Status.READY},
        )
        self.assertEqual(resp.status_code, 302)
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, Room.Status.READY)

    def test_hk_report_maintenance_creates_ticket(self):
        url = reverse("housekeeping:report_maintenance", args=[self.room.pk])
        resp = self.client.post(url, {"title": "Konditsioner ishlamayapti"})
        self.assertEqual(resp.status_code, 302)
        ticket = MaintenanceTicket.objects.get(tenant=self.tenant, room=self.room)
        self.assertEqual(ticket.title, "Konditsioner ishlamayapti")
        self.assertEqual(ticket.status, MaintenanceTicket.Status.OPEN)

    def test_hk_report_maintenance_can_set_ooo(self):
        url = reverse("housekeeping:report_maintenance", args=[self.room.pk])
        self.client.post(url, {"title": "Suv oqishi", "set_ooo": "1"})
        self.room.refresh_from_db()
        ticket = MaintenanceTicket.objects.get(tenant=self.tenant, room=self.room)
        self.assertTrue(ticket.set_room_ooo)
        self.assertEqual(self.room.status, Room.Status.OUT_OF_ORDER)
