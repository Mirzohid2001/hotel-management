"""Ko‘p filial (multi-branch) funksiyalari — to‘liq tekshiruv."""

from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.services import create_reservation
from core.tests.helpers import make_membership, make_user, setup_tenant_user
from guests.models import Guest
from properties.active import ALL_PROPERTIES, SESSION_PROPERTY_KEY
from properties.models import Property, PropertySettings, RatePlan, Room, RoomType
from reports.day_lock import is_day_locked, is_property_day_locked
from reports.night_audit import run_night_audit
from subscriptions.models import Plan
from tenants.models import MembershipProperty, TenantMembership
from widget.models import WidgetConfig

from bookings.services import generate_reservation_code


class BranchCodeTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(username="branchcode")
        self.tenant = self.ctx["tenant"]

    def test_branch_code_auto_generated(self):
        prop = Property.objects.create(tenant=self.tenant, name="Toshkent Shahri")
        self.assertTrue(prop.branch_code)
        self.assertEqual(prop.branch_code, "toshkent-shahri")

    def test_display_label_includes_code(self):
        prop = Property.objects.create(tenant=self.tenant, name="Chilanzar", branch_code="chl")
        self.assertEqual(prop.display_label, "Chilanzar (CHL)")

    def test_reservation_code_uses_branch_prefix(self):
        prop = Property.objects.create(tenant=self.tenant, name="Tash", branch_code="tsh")
        code = generate_reservation_code(self.tenant, prop)
        self.assertTrue(code.startswith("TSH-"))
        self.assertIn(str(timezone.localdate().year), code)


class PropertySwitcherTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="switcher")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.client = Client()
        self.client.force_login(self.user)
        self.prop_a = Property.objects.create(tenant=self.tenant, name="Filial A")
        self.prop_b = Property.objects.create(tenant=self.tenant, name="Filial B")

    def test_switch_all_sets_session(self):
        resp = self.client.post(reverse("properties:switch_all"), {"next": "/"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.client.session.get(SESSION_PROPERTY_KEY), ALL_PROPERTIES)

    def test_switch_all_requires_two_properties(self):
        self.prop_b.is_active = False
        self.prop_b.save()
        resp = self.client.post(reverse("properties:switch_all"))
        self.assertEqual(resp.status_code, 302)
        self.assertNotEqual(self.client.session.get(SESSION_PROPERTY_KEY), ALL_PROPERTIES)

    def test_switch_single_property(self):
        resp = self.client.post(
            reverse("properties:switch", args=[self.prop_b.pk]),
            {"next": "/"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.client.session.get(SESSION_PROPERTY_KEY), self.prop_b.pk)

    def test_all_mode_dashboard_aggregates(self):
        PropertySettings.objects.create(
            tenant=self.tenant, property=self.prop_a, require_id_on_checkin=False
        )
        PropertySettings.objects.create(
            tenant=self.tenant, property=self.prop_b, require_id_on_checkin=False
        )
        rt_a = RoomType.objects.create(
            tenant=self.tenant, property=self.prop_a, name="A", code="a", base_price=1
        )
        rt_b = RoomType.objects.create(
            tenant=self.tenant, property=self.prop_b, name="B", code="b", base_price=1
        )
        Room.objects.create(tenant=self.tenant, property=self.prop_a, room_type=rt_a, number="A1")
        Room.objects.create(tenant=self.tenant, property=self.prop_b, room_type=rt_b, number="B1")

        self.client.post(reverse("properties:switch_all"))
        resp = self.client.get(reverse("reports:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Barcha filiallar")

    def test_night_audit_blocked_in_all_mode(self):
        self.client.post(reverse("properties:switch_all"))
        resp = self.client.post(reverse("reports:night_audit"))
        self.assertEqual(resp.status_code, 302)
        follow = self.client.get(reverse("reports:dashboard"))
        self.assertContains(follow, "filial tanlang", status_code=200)


class StaffPropertyAccessTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="owner")
        self.tenant = self.ctx["tenant"]
        self.prop_a = Property.objects.create(tenant=self.tenant, name="A Filial")
        self.prop_b = Property.objects.create(tenant=self.tenant, name="B Filial")
        self.manager = make_user(username="mgr_branch", password="pass12345")
        self.membership = make_membership(
            self.manager, self.tenant, role=TenantMembership.Role.MANAGER
        )
        MembershipProperty.objects.create(membership=self.membership, property=self.prop_a)

    def test_restricted_manager_cannot_switch_to_other_branch(self):
        client = Client()
        client.force_login(self.manager)
        resp = client.post(reverse("properties:switch", args=[self.prop_b.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertNotEqual(client.session.get(SESSION_PROPERTY_KEY), self.prop_b.pk)

    def test_restricted_manager_sidebar_shows_only_assigned(self):
        client = Client()
        client.force_login(self.manager)
        resp = client.get(reverse("reports:dashboard"))
        self.assertContains(resp, self.prop_a.display_label)
        self.assertNotContains(resp, self.prop_b.display_label)

    def test_admin_sees_all_branches_in_sidebar(self):
        client = Client()
        client.force_login(self.ctx["user"])
        resp = client.get(reverse("reports:dashboard"))
        self.assertContains(resp, self.prop_a.display_label)
        self.assertContains(resp, self.prop_b.display_label)

    def test_property_detail_denied_for_restricted_branch(self):
        client = Client()
        client.force_login(self.manager)
        resp = client.get(reverse("properties:detail", args=[self.prop_b.pk]))
        self.assertEqual(resp.status_code, 404)


class PropertyLimitTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.FREE, username="freelim")
        self.tenant = self.ctx["tenant"]
        self.client = Client()
        self.client.force_login(self.ctx["user"])
        Property.objects.create(tenant=self.tenant, name="Only One")

    def test_free_plan_blocks_second_property(self):
        resp = self.client.post(
            reverse("properties:create"),
            {
                "name": "Second Branch",
                "branch_code": "",
                "address": "",
                "city": "",
                "phone": "",
                "email": "",
                "is_active": "on",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Property.objects.filter(tenant=self.tenant).count(), 1)


class PerPropertyNightAuditTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="peraudit")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.today = timezone.localdate()
        self.prop_a = Property.objects.create(tenant=self.tenant, name="Audit A")
        self.prop_b = Property.objects.create(tenant=self.tenant, name="Audit B")
        for prop, num in ((self.prop_a, "101"), (self.prop_b, "201")):
            PropertySettings.objects.create(
                tenant=self.tenant, property=prop, require_id_on_checkin=False
            )
            rt = RoomType.objects.create(
                tenant=self.tenant, property=prop, name="Std", code="s", base_price=Decimal("100000")
            )
            Room.objects.create(tenant=self.tenant, property=prop, room_type=rt, number=num)
            RatePlan.objects.create(
                tenant=self.tenant,
                property=prop,
                room_type=rt,
                name="BAR",
                code="bar",
                price=Decimal("100000"),
            )

    def test_night_audit_per_branch_isolated(self):
        run_night_audit(self.tenant, self.user, audit_date=self.today, hotel=self.prop_a)
        self.assertTrue(is_property_day_locked(self.tenant, self.today, self.prop_a))
        self.assertFalse(is_property_day_locked(self.tenant, self.today, self.prop_b))
        self.assertFalse(is_day_locked(self.tenant, self.today))

        run_night_audit(self.tenant, self.user, audit_date=self.today, hotel=self.prop_b)
        self.assertTrue(is_day_locked(self.tenant, self.today))


class WidgetPerBranchTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="wgtbranch")
        self.tenant = self.ctx["tenant"]

    def test_widget_config_created_on_property_save(self):
        prop = Property.objects.create(tenant=self.tenant, name="Widget Branch")
        self.assertTrue(WidgetConfig.objects.filter(hotel=prop, tenant=self.tenant).exists())

    def test_two_branches_have_separate_widgets(self):
        a = Property.objects.create(tenant=self.tenant, name="W A")
        b = Property.objects.create(tenant=self.tenant, name="W B")
        cfg_a = WidgetConfig.objects.get(hotel=a)
        cfg_b = WidgetConfig.objects.get(hotel=b)
        cfg_a.is_enabled = True
        cfg_a.save()
        self.assertNotEqual(cfg_a.public_key, cfg_b.public_key)
        self.assertIn(a.branch_code, cfg_a.widget_path)
        self.assertIn(b.branch_code, cfg_b.widget_path)

    def test_legacy_widget_url_redirects_to_branch(self):
        prop = Property.objects.create(tenant=self.tenant, name="Legacy")
        cfg = WidgetConfig.objects.get(hotel=prop)
        cfg.is_enabled = True
        cfg.save()
        resp = Client().get(reverse("widget:frame_legacy", args=[self.tenant.slug]))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(prop.branch_code, resp.url)


class ReservationCodeIsolationTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="codeiso")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.today = timezone.localdate()
        self.prop_a = Property.objects.create(tenant=self.tenant, name="Code A", branch_code="ca")
        self.prop_b = Property.objects.create(tenant=self.tenant, name="Code B", branch_code="cb")
        for prop, code in ((self.prop_a, "ca"), (self.prop_b, "cb")):
            PropertySettings.objects.create(
                tenant=self.tenant, property=prop, require_id_on_checkin=False
            )
            rt = RoomType.objects.create(
                tenant=self.tenant, property=prop, name="S", code=code, base_price=1
            )
            Room.objects.create(tenant=self.tenant, property=prop, room_type=rt, number="1")
            RatePlan.objects.create(
                tenant=self.tenant,
                property=prop,
                room_type=rt,
                name="BAR",
                code=f"bar-{code}",
                price=1,
            )
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="G")

    def test_separate_sequences_per_branch(self):
        stack_a = self.prop_a
        rt_a = stack_a.room_types.first()
        room_a = stack_a.rooms.first()
        rate_a = stack_a.rate_plans.first()
        r1 = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=stack_a,
            guest=self.guest,
            room_type=rt_a,
            room=room_a,
            rate_plan=rate_a,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
        )
        stack_b = self.prop_b
        rt_b = stack_b.room_types.first()
        room_b = stack_b.rooms.first()
        rate_b = stack_b.rate_plans.first()
        r2 = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=stack_b,
            guest=self.guest,
            room_type=rt_b,
            room=room_b,
            rate_plan=rate_b,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
        )
        self.assertTrue(r1.code.startswith("CA-"))
        self.assertTrue(r2.code.startswith("CB-"))
        self.assertTrue(r1.code.endswith("-0001"))
        self.assertTrue(r2.code.endswith("-0001"))
