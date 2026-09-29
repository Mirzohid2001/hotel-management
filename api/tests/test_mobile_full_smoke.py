"""Full mobile API surface smoke — every screen's primary endpoints."""

from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import BookingReferrer
from bookings.services import check_in_reservation, create_reservation
from core.tests.helpers import setup_tenant_user
from finance.models import Expense, ExpenseCategory
from guests.models import Guest
from properties.models import Property, PropertySettings, RatePlan, Room, RoomType
from subscriptions.models import Plan
from tenants.models import TenantMembership


class MobileFullSmokeTests(TestCase):
    """Admin role + seeded hotel: hit all mobile-facing GET/print endpoints + key writes."""

    def setUp(self):
        self.ctx = setup_tenant_user(
            plan_code=Plan.Code.PRO,
            role=TenantMembership.Role.ADMIN,
            username="mobsmoke",
        )
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.password = "pass12345"
        self.user.set_password(self.password)
        self.user.save()
        self.prop = Property.objects.create(tenant=self.tenant, name="Smoke Hotel")
        PropertySettings.objects.create(
            tenant=self.tenant,
            property=self.prop,
            emehmon_fee=Decimal("9000"),
            require_id_on_checkin=False,
        )
        self.rt = RoomType.objects.create(
            tenant=self.tenant,
            property=self.prop,
            name="Std",
            code="std",
            base_price=Decimal("200000"),
        )
        self.room = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="101"
        )
        self.room2 = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="102"
        )
        self.guest = Guest.objects.create(
            tenant=self.tenant, first_name="Ali", last_name="Valiyev", phone="99890"
        )
        self.today = timezone.localdate()
        self.rate = RatePlan.objects.create(
            tenant=self.tenant,
            property=self.prop,
            room_type=self.rt,
            name="BAR",
            code="bar",
            price=Decimal("200000"),
            is_default=True,
        )
        self.referrer = BookingReferrer.objects.create(
            tenant=self.tenant,
            name="Agent",
            phone="99891",
            default_commission_percent=Decimal("10"),
        )
        self.cat = ExpenseCategory.objects.create(tenant=self.tenant, name="Office")
        self.expense = Expense.objects.create(
            tenant=self.tenant,
            hotel=self.prop,
            category=self.cat,
            title="Paper",
            amount=Decimal("15000"),
            expense_date=self.today,
        )
        self.reservation = create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            check_in=self.today,
            check_out=self.today + timedelta(days=2),
            adults=1,
        )
        check_in_reservation(self.reservation, self.user)
        self.reservation.refresh_from_db()
        self.client = Client()
        self.token = self._login()
        self.h = {
            "HTTP_AUTHORIZATION": f"Bearer {self.token}",
            "HTTP_X_HOTEL_ID": str(self.prop.pk),
            "HTTP_X_TENANT_ID": str(self.tenant.pk),
        }
        self.hp = {**self.h, "content_type": "application/json"}

    def _login(self):
        resp = self.client.post(
            reverse("api:login"),
            data=json.dumps({"username": "mobsmoke", "password": self.password}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.json()["data"]["token"]

    def _get(self, name, *, args=None, qs="", expect=200):
        url = reverse(f"api:{name}", args=args or ())
        if qs:
            url = f"{url}?{qs}"
        resp = self.client.get(url, **self.h)
        self.assertEqual(
            resp.status_code,
            expect,
            f"GET {name} -> {resp.status_code}: {resp.content[:400]!r}",
        )
        body = resp.json()
        self.assertTrue(body.get("ok"), f"GET {name} not ok: {body}")
        return body["data"]

    def _post(self, name, payload=None, *, args=None, expect=(200, 201)):
        url = reverse(f"api:{name}", args=args or ())
        resp = self.client.post(
            url,
            data=json.dumps(payload or {}),
            **self.hp,
        )
        allowed = (expect,) if isinstance(expect, int) else tuple(expect)
        self.assertIn(
            resp.status_code,
            allowed,
            f"POST {name} -> {resp.status_code}: {resp.content[:400]!r}",
        )
        body = resp.json()
        self.assertTrue(body.get("ok"), f"POST {name} not ok: {body}")
        return body["data"]

    def test_01_auth_me_board_today(self):
        me = self._get("me")
        self.assertEqual(me["user"]["username"], "mobsmoke")
        board = self._get("board")
        self.assertGreaterEqual(board["stats"]["total"], 1)
        self._get("today")
        self._post("me_update", {"first_name": "Smoke"})

    def test_02_ops_screens(self):
        self._get("inquiries")
        self._get("calendar", qs="days=14")
        self._get("calendar", qs="days=30")
        self._get("housekeeping_board")
        self._get("housekeeping_staff")
        self._get("maintenance_list")
        self._get("notifications")
        dismissable = self._get("notifications")
        items = dismissable.get("items") or []
        if items:
            self._post("notifications_dismiss", {"key": items[0]["key"]})

    def test_03_reports_prints_exports(self):
        self._get("flash_report")
        flash_pdf = self._get("flash_print")
        self.assertIn("pdf_base64", flash_pdf)
        self.assertTrue(len(flash_pdf["pdf_base64"]) > 100)
        self._get("dashboard_report")
        self._get("report_history")
        self._get("pnl_report")
        pnl_pdf = self._get("pnl_print")
        self.assertIn("pdf_base64", pnl_pdf)
        self._get("emehmon_report", qs=f"year={self.today.year}&month={self.today.month}")
        self._get("commission_report")
        comm_pdf = self._get("commission_print", args=[self.referrer.pk])
        self.assertIn("pdf_base64", comm_pdf)
        self._get("night_audit_status")
        self._get("audit_log")
        for name in ("export_payments_csv", "export_pnl_csv", "export_ar_csv"):
            data = self._get(name)
            self.assertIn("content_base64", data)

    def test_04_cash_services_minibar(self):
        self._get("cash_shift_status")
        opened = self._post("cash_shift_open", {"opening_float": "100000"})
        shift_id = opened["shift"]["id"]
        self._post(
            "cash_shift_movement",
            {"kind": "pay_in", "amount": "5000", "note": "smoke"},
        )
        pdf = self._get("cash_shift_print", args=[shift_id])
        self.assertIn("pdf_base64", pdf)
        self._get("cash_shift_history")
        self._get("service_list")
        self._get("service_orders_recent")
        self._get("minibar_items")

    def test_05_reservation_folio_flow(self):
        self._post("cash_shift_open", {"opening_float": "50000"})
        rid = self.reservation.pk
        detail = self._get("reservation_detail", args=[rid])
        self.assertEqual(detail["id"], rid)
        folio = detail.get("folio") or {}
        self.assertTrue(folio.get("id"))
        receipt = self._get("folio_receipt", args=[folio["id"]], qs="pdf=1")
        self.assertIn("pdf_base64", receipt)
        self._post(
            "reservation_payment",
            {"amount": "50000", "method": "cash"},
            args=[rid],
        )
        self._post(
            "reservation_charge",
            {
                "description": "Extra",
                "unit_price": "10000",
                "quantity": "1",
            },
            args=[rid],
        )
        self._post("reservation_notes", {"notes": "smoke ok"}, args=[rid])
        self._get("reservations_list")
        self._get("reservation_search", qs="q=Ali")
        self._get(
            "rooms_available",
            qs=f"check_in={self.today}&check_out={self.today + timedelta(days=1)}",
        )

    def test_06_guests_companies_groups_ledger(self):
        self._get("guest_list", qs="q=Ali")
        self._get("guest_detail", args=[self.guest.pk])
        self._post(
            "guest_detail",
            {"first_name": "Ali", "last_name": "Valiyev", "is_vip": True},
            args=[self.guest.pk],
        )
        self._get("companies")
        co = self._post(
            "company_create",
            {"name": "Smoke Co", "phone": "998"},
            expect=201,
        )
        self._get("company_update", args=[co["id"]])
        self._get("city_ledger")
        self._get("groups")

    def test_07_finance_hr_inventory_setup(self):
        self._get("expenses")
        self._get("expenses_meta")
        exp_pdf = self._get("expense_print", args=[self.expense.pk])
        self.assertIn("pdf_base64", exp_pdf)
        self._get("fx_list")
        self._get("profit_ledger")
        self._get("profit_partners")
        self._get("inventory_items")
        self._get("inventory_low_stock")
        self._get("referrers")
        self._get("hr_employees")
        self._get("hr_advances")
        self._get("hr_payroll_status")
        self._get("staff_list")
        self._get("staff_meta")
        self._get("property_settings")
        self._get("room_types")
        self._get("rooms_admin")
        self._get("floors_admin")
        self._get("services_catalog")
        self._get("rate_plans")
        matrix = self._get("rate_plan_matrix", args=[self.rate.pk], qs="days=42")
        self.assertTrue(matrix.get("rows"))
        self._post(
            "rate_plan_season_create",
            {
                "name": "Smoke day",
                "date_from": self.today.isoformat(),
                "date_to": self.today.isoformat(),
                "price": "250000",
            },
            args=[self.rate.pk],
            expect=(200, 201),
        )

    def test_08_walk_in_and_checkout(self):
        self._post("cash_shift_open", {"opening_float": "100000"})
        walk = self._post(
            "walk_in",
            {
                "room_id": self.room2.pk,
                "first_name": "Walk",
                "last_name": "In",
                "nights": 1,
                "adults": 1,
                "collect_emehmon": False,
            },
        )
        self.assertTrue(walk.get("reservation_id") or walk.get("id"))
        rid = walk.get("reservation_id") or walk.get("id")
        self._post(
            "reservation_payment",
            {"amount": "500000", "method": "cash"},
            args=[rid],
        )
        resp = self.client.post(
            reverse("api:reservation_check_out", args=[rid]),
            data="{}",
            **self.hp,
        )
        self.assertIn(resp.status_code, (200, 400), resp.content)
