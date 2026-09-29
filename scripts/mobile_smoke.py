#!/usr/bin/env python3
"""Full mobile API smoke against local DB (demo / demo12345).

Usage:
  ./venv/bin/python scripts/mobile_smoke.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.test import Client
from django.utils import timezone

from accounts.models import User
from properties.models import Property, Room
from tenants.models import TenantMembership


BASE = "/api/v1"
PASS = "demo12345"


class Smoke:
    def __init__(self):
        self.c = Client()
        self.token = None
        self.hotel_id = None
        self.tenant_id = None
        self.ok = []
        self.fail = []
        self.skip = []

    def headers(self):
        h = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}
        if self.tenant_id:
            h["HTTP_X_TENANT_ID"] = str(self.tenant_id)
        if self.hotel_id:
            h["HTTP_X_HOTEL_ID"] = str(self.hotel_id)
        return h

    def req(self, method, path, *, label=None, expect=(200,), body=None, allow_fail=False):
        name = label or f"{method} {path}"
        url = path if path.startswith("/") else f"{BASE}/{path}"
        if not url.startswith(BASE) and url.startswith("/api"):
            pass
        elif not url.startswith(BASE):
            url = f"{BASE}{path if path.startswith('/') else '/' + path}"
        kw = {**self.headers()}
        if body is not None:
            kw["data"] = json.dumps(body)
            kw["content_type"] = "application/json"
        try:
            resp = getattr(self.c, method.lower())(url, **kw)
        except Exception as exc:  # noqa: BLE001
            self.fail.append((name, f"EXC {exc}"))
            print(f"  FAIL {name}: EXC {exc}")
            return None
        status = resp.status_code
        try:
            payload = resp.json()
        except Exception:
            payload = {"raw": resp.content[:200].decode("utf-8", "replace")}
        ok_flag = status in expect and (
            isinstance(payload, dict) and payload.get("ok") is True
            if status < 400
            else True
        )
        # Some endpoints return ok:false with 4xx — treat expected statuses as soft ok
        if status in expect:
            if isinstance(payload, dict) and payload.get("ok") is False and not allow_fail:
                # still count as pass if HTTP status was in expect and we allowed business error
                if status >= 400:
                    ok_flag = True
                else:
                    ok_flag = False
            else:
                ok_flag = True
        if ok_flag:
            self.ok.append(name)
            print(f"  OK   {name} [{status}]")
            return payload.get("data") if isinstance(payload, dict) else payload
        msg = payload.get("error") if isinstance(payload, dict) else payload
        if allow_fail:
            self.skip.append((name, f"{status} {msg}"))
            print(f"  SKIP {name} [{status}] {msg}")
            return None
        self.fail.append((name, f"{status} {msg}"))
        print(f"  FAIL {name} [{status}] {msg}")
        return None

    def get(self, path, **kw):
        return self.req("get", path, **kw)

    def post(self, path, body=None, **kw):
        return self.req("post", path, body=body or {}, **kw)

    def login(self):
        user = User.objects.filter(username="demo").first()
        if user is None:
            print("ERROR: demo user yo‘q — seed_demo ishga tushiring")
            sys.exit(2)
        # Prefer Rivoj Hotel property if present
        membership = (
            TenantMembership.objects.filter(user=user, is_active=True)
            .select_related("tenant")
            .first()
        )
        if membership is None:
            print("ERROR: demo membership yo‘q")
            sys.exit(2)
        self.tenant_id = membership.tenant_id
        prop = (
            Property.objects.filter(tenant_id=self.tenant_id, is_active=True)
            .order_by("id")
            .first()
        )
        # Prefer named Rivoj
        rivoj = Property.objects.filter(
            tenant_id=self.tenant_id, name__icontains="Rivoj"
        ).first()
        if rivoj:
            prop = rivoj
        self.hotel_id = prop.pk if prop else None
        print(f"Tenant={self.tenant_id} Hotel={self.hotel_id} ({getattr(prop, 'name', None)})")

        resp = self.c.post(
            f"{BASE}/auth/login/",
            data=json.dumps({"username": "demo", "password": PASS}),
            content_type="application/json",
        )
        body = resp.json()
        if not body.get("ok"):
            print("LOGIN FAIL", body)
            sys.exit(2)
        self.token = body["data"]["token"]
        self.ok.append("POST /auth/login/")
        print("  OK   POST /auth/login/")

    def run_reads(self):
        print("\n=== READ screens (mobile parity) ===")
        self.get("/me/", label="me")
        self.get("/board/", label="board")
        self.get("/today/", label="today")
        self.get("/inquiries/", label="inquiries")
        self.get("/calendar/?days=14", label="calendar 14")
        self.get("/calendar/?days=30", label="calendar 30")
        self.get("/housekeeping/", label="housekeeping")
        self.get("/housekeeping/staff/", label="hk staff")
        self.get("/maintenance/", label="maintenance")
        self.get("/notifications/", label="notifications")
        self.get("/reports/flash/", label="flash")
        self.get("/reports/flash/print/", label="flash print PDF")
        self.get("/reports/dashboard/", label="dashboard")
        self.get("/reports/history/", label="report history")
        self.get("/reports/pnl/", label="pnl")
        self.get("/reports/pnl/print/", label="pnl print PDF")
        self.get("/reports/emehmon/", label="emehmon")
        today = timezone.localdate()
        self.get(
            f"/reports/emehmon/?year={today.year}&month={today.month}",
            label="emehmon month",
        )
        self.get("/reports/commission/", label="commission")
        self.get("/reports/night-audit/", label="night-audit status")
        self.get("/reports/audit/", label="audit log")
        self.get("/export/payments.csv/", label="export payments csv")
        self.get("/export/pnl.csv/", label="export pnl csv")
        self.get("/export/ar.csv/", label="export ar csv")
        self.get("/cash-shift/", label="cash shift")
        self.get("/cash-shift/history/", label="cash history")
        self.get("/services/", label="services")
        self.get("/services/orders/", label="service orders")
        self.get("/minibar/items/", label="minibar items")
        self.get("/guests/?q=a", label="guests search")
        self.get("/reservations/search/?q=HTL", label="res search")
        self.get("/reservations/list/", label="res list")
        self.get("/companies/", label="companies")
        self.get("/city-ledger/", label="city ledger")
        self.get("/groups/", label="groups")
        self.get("/expenses/", label="expenses")
        self.get("/expenses/meta/", label="expenses meta")
        self.get("/fx/", label="fx")
        self.get("/profit/", label="profit")
        self.get("/profit/partners/", label="profit partners")
        self.get("/inventory/items/", label="inventory")
        self.get("/inventory/low-stock/", label="low stock")
        self.get("/referrers/", label="referrers")
        self.get("/hr/employees/", label="hr employees")
        self.get("/hr/advances/", label="hr advances")
        self.get("/hr/payroll/", label="hr payroll")
        self.get("/staff/", label="staff")
        self.get("/staff/meta/", label="staff meta")
        self.get("/setup/settings/", label="setup settings")
        self.get("/setup/room-types/", label="setup room types")
        self.get("/setup/rooms/", label="setup rooms")
        self.get("/setup/floors/", label="setup floors")
        self.get("/setup/services/", label="setup services")
        self.get("/setup/rate-plans/", label="setup rate plans")

    def run_detail_chains(self):
        print("\n=== DETAIL chains ===")
        board = self.get("/board/", label="board (detail)")
        res_id = None
        room_id = None
        if board:
            for t in board.get("tiles") or []:
                if t.get("reservation") and not res_id:
                    res_id = t["reservation"].get("id")
                if t.get("room") and not room_id:
                    room_id = t["room"].get("id")
        if not res_id:
            # fall back to list
            lst = self.get("/reservations/list/", label="res list fallback")
            items = (lst or {}).get("items") or []
            if items:
                res_id = items[0].get("id")
        if res_id:
            detail = self.get(f"/reservations/{res_id}/", label=f"reservation {res_id}")
            folio = (detail or {}).get("folio") or {}
            folio_id = folio.get("id")
            if folio_id:
                self.get(
                    f"/folios/{folio_id}/receipt/?pdf=1",
                    label=f"folio {folio_id} receipt+pdf",
                )
            guest = (detail or {}).get("guest") or {}
            if guest.get("id"):
                self.get(f"/guests/{guest['id']}/", label=f"guest {guest['id']}")
        else:
            self.skip.append(("reservation detail", "no reservation in DB"))
            print("  SKIP reservation detail — bron yo‘q")

        companies = self.get("/companies/", label="companies (detail)")
        items = (companies or {}).get("items") or companies or []
        if isinstance(items, list) and items:
            cid = items[0].get("id")
            if cid:
                self.get(f"/companies/{cid}/", label=f"company {cid}")

        rates = self.get("/setup/rate-plans/", label="rate plans (matrix)")
        rate_items = (rates or {}).get("items") or []
        if rate_items:
            rid = rate_items[0].get("id")
            self.get(
                f"/setup/rate-plans/{rid}/matrix/?days=42",
                label=f"rate matrix {rid}",
            )

        hist = self.get("/cash-shift/history/", label="cash hist (print)")
        hist_items = (hist or {}).get("items") or []
        if hist_items:
            sid = hist_items[0].get("id")
            self.get(f"/cash-shift/{sid}/print/", label=f"cash print {sid}")
        elif board:
            # open shift maybe
            shift = self.get("/cash-shift/", label="cash for print id")
            s = (shift or {}).get("shift") or shift
            if isinstance(s, dict) and s.get("id"):
                self.get(
                    f"/cash-shift/{s['id']}/print/",
                    label=f"cash print open {s['id']}",
                )

        expenses = self.get("/expenses/", label="expenses (print)")
        exp_items = (expenses or {}).get("items") or []
        if exp_items:
            eid = exp_items[0].get("id")
            self.get(f"/expenses/{eid}/print/", label=f"expense print {eid}")

        refs = self.get("/referrers/", label="referrers (print)")
        ref_items = (refs or {}).get("items") or []
        if ref_items:
            rfid = ref_items[0].get("id")
            self.get(
                f"/reports/commission/{rfid}/print/",
                label=f"commission print {rfid}",
            )

        cl = self.get("/city-ledger/", label="city ledger (detail)")
        cl_items = (cl or {}).get("items") or []
        if cl_items:
            iid = cl_items[0].get("id")
            self.get(f"/city-ledger/{iid}/?pdf=1", label=f"city ledger {iid} pdf")

        notes = self.get("/notifications/", label="notifications dismiss probe")
        n_items = (notes or {}).get("items") or []
        if n_items:
            key = n_items[0].get("key")
            self.post(
                "/notifications/dismiss/",
                body={"key": key},
                label=f"dismiss {key[:24]}",
            )

    def run_safe_writes(self):
        print("\n=== SAFE writes (non-destructive) ===")
        # profile touch (same values)
        me = self.get("/me/", label="me before update")
        if me:
            self.post(
                "/me/update/",
                body={"first_name": me.get("first_name") or "Demo"},
                label="me update",
            )

        # notes on a reservation if any
        lst = self.get("/reservations/list/", label="res for notes")
        items = (lst or {}).get("items") or []
        if items:
            rid = items[0]["id"]
            self.post(
                f"/reservations/{rid}/notes/",
                body={"notes": "smoke-test note"},
                label=f"notes {rid}",
                allow_fail=True,
            )

        # create expense draft then leave (or delete if possible)
        meta = self.get("/expenses/meta/", label="exp meta write")
        cats = (meta or {}).get("categories") or []
        cat_id = cats[0]["id"] if cats else None
        if cat_id:
            created = self.post(
                "/expenses/create/",
                body={
                    "title": "Smoke test expense",
                    "amount": "1000",
                    "category_id": cat_id,
                },
                label="expense create",
                allow_fail=True,
            )
            if created and created.get("id"):
                eid = created["id"]
                self.post(
                    f"/expenses/{eid}/delete/",
                    body={},
                    label=f"expense delete {eid}",
                    allow_fail=True,
                )

        # available rooms for tomorrow
        day = timezone.localdate()
        self.get(
            f"/rooms/available/?check_in={day}&check_out={day + timedelta(days=1)}",
            label="rooms available",
        )

    def summary(self):
        print("\n=== SUMMARY ===")
        print(f"OK:   {len(self.ok)}")
        print(f"SKIP: {len(self.skip)}")
        print(f"FAIL: {len(self.fail)}")
        if self.fail:
            print("\nFailures:")
            for name, err in self.fail:
                print(f"  - {name}: {err}")
        return 0 if not self.fail else 1


def main():
    s = Smoke()
    s.login()
    s.run_reads()
    s.run_detail_chains()
    s.run_safe_writes()
    raise SystemExit(s.summary())


if __name__ == "__main__":
    main()
