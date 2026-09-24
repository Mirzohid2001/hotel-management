from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.services import create_reservation
from core.tests.helpers import setup_tenant_user
from guests.models import Guest
from properties.models import Property, PropertySettings, Room, RoomType
from subscriptions.models import Plan
from tenants.models import TenantMembership


class ApiAuthBoardTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="apiuser")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.password = "pass12345"
        self.user.set_password(self.password)
        self.user.save()
        TenantMembership.objects.filter(user=self.user, tenant=self.tenant).update(
            role=TenantMembership.Role.RECEPTIONIST
        )
        self.prop = Property.objects.create(tenant=self.tenant, name="API Hotel")
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
            base_price=Decimal("100000"),
        )
        self.room = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="101"
        )
        self.guest = Guest.objects.create(tenant=self.tenant, first_name="Ali")
        self.today = timezone.localdate()
        self.client = Client()

    def _login(self):
        resp = self.client.post(
            reverse("api:login"),
            data='{"username":"apiuser","password":"pass12345"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body["ok"])
        return body["data"]["token"]

    def test_login_and_board(self):
        create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
            adults=1,
        )
        token = self._login()
        resp = self.client.get(
            reverse("api:board"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_HOTEL_ID=str(self.prop.pk),
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()["data"]
        self.assertEqual(data["stats"]["total"], 1)
        self.assertEqual(len(data["tiles"]), 1)
        self.assertEqual(data["tiles"][0]["room"]["number"], "101")

    def test_board_requires_auth(self):
        resp = self.client.get(reverse("api:board"))
        self.assertEqual(resp.status_code, 401)

    def test_me(self):
        token = self._login()
        resp = self.client.get(
            reverse("api:me"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(resp.status_code, 200)
        me = resp.json()["data"]
        self.assertEqual(me["tenant"]["id"], self.tenant.pk)
        self.assertEqual(me["role"], TenantMembership.Role.RECEPTIONIST)
        self.assertTrue(any(h["id"] == self.prop.pk for h in me["hotels"]))

    def test_walk_in_and_payment(self):
        token = self._login()
        headers = {
            "HTTP_AUTHORIZATION": f"Bearer {token}",
            "HTTP_X_HOTEL_ID": str(self.prop.pk),
            "content_type": "application/json",
        }
        walk = self.client.post(
            reverse("api:walk_in"),
            data='{"room_id":%d,"first_name":"Dilshod","nights":1,"adults":1,"allow_no_docs":true}'
            % self.room.pk,
            **headers,
        )
        self.assertEqual(walk.status_code, 201, walk.content)
        body = walk.json()["data"]
        self.assertEqual(body["status"], "checked_in")
        rid = body["reservation_id"]

        pay = self.client.post(
            reverse("api:reservation_payment", kwargs={"pk": rid}),
            data='{"amount":"50000","method":"card"}',
            **headers,
        )
        self.assertEqual(pay.status_code, 201, pay.content)
        pay_data = pay.json()["data"]
        self.assertEqual(pay_data["method"], "card")
        self.assertEqual(Decimal(pay_data["amount"]), Decimal("50000"))

        detail = self.client.get(
            reverse("api:reservation_detail", kwargs={"pk": rid}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_HOTEL_ID=str(self.prop.pk),
        )
        self.assertEqual(detail.status_code, 200, detail.content)
        folio = detail.json()["data"]["folio"]
        self.assertIsNotNone(folio)
        self.assertTrue(any(p["method"] == "card" for p in folio["payments"]))

        charge = self.client.post(
            reverse("api:reservation_charge", kwargs={"pk": rid}),
            data='{"description":"Minibar","unit_price":"15000","charge_type":"minibar"}',
            **headers,
        )
        self.assertEqual(charge.status_code, 201, charge.content)

    def test_room_status_and_service(self):
        from services.models import ServiceItem

        self.room.status = "dirty"
        self.room.save(update_fields=["status", "updated_at"])
        svc = ServiceItem.objects.create(
            tenant=self.tenant,
            name="Laundry",
            code="laundry",
            unit_price=Decimal("25000"),
        )
        token = self._login()
        headers = {
            "HTTP_AUTHORIZATION": f"Bearer {token}",
            "HTTP_X_HOTEL_ID": str(self.prop.pk),
            "content_type": "application/json",
        }
        status_resp = self.client.post(
            reverse("api:room_set_status", kwargs={"pk": self.room.pk}),
            data='{"status":"ready"}',
            **headers,
        )
        self.assertEqual(status_resp.status_code, 200, status_resp.content)
        self.assertEqual(status_resp.json()["data"]["status"], "ready")

        walk = self.client.post(
            reverse("api:walk_in"),
            data='{"room_id":%d,"first_name":"Sara","nights":1,"allow_no_docs":true}'
            % self.room.pk,
            **headers,
        )
        self.assertEqual(walk.status_code, 201, walk.content)
        rid = walk.json()["data"]["reservation_id"]

        catalog = self.client.get(
            reverse("api:service_list"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_HOTEL_ID=str(self.prop.pk),
        )
        self.assertEqual(catalog.status_code, 200)
        self.assertTrue(
            any(i["id"] == svc.pk for i in catalog.json()["data"]["items"])
        )

        order = self.client.post(
            reverse("api:reservation_service", kwargs={"pk": rid}),
            data='{"service_id":%d,"quantity":"1"}' % svc.pk,
            **headers,
        )
        self.assertEqual(order.status_code, 201, order.content)
        self.assertEqual(Decimal(order.json()["data"]["amount"]), Decimal("25000"))

    def test_today_search_extend_transfer(self):
        room2 = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="102"
        )
        create_reservation(
            tenant=self.tenant,
            user=self.user,
            property_obj=self.prop,
            guest=self.guest,
            room_type=self.rt,
            room=self.room,
            check_in=self.today,
            check_out=self.today + timedelta(days=1),
            adults=1,
        )
        token = self._login()
        headers = {
            "HTTP_AUTHORIZATION": f"Bearer {token}",
            "HTTP_X_HOTEL_ID": str(self.prop.pk),
            "content_type": "application/json",
        }

        today_resp = self.client.get(
            reverse("api:today"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_HOTEL_ID=str(self.prop.pk),
        )
        self.assertEqual(today_resp.status_code, 200, today_resp.content)
        today_data = today_resp.json()["data"]
        self.assertGreaterEqual(today_data["counts"]["arrivals"], 1)

        search = self.client.get(
            reverse("api:reservation_search") + "?q=Ali",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_HOTEL_ID=str(self.prop.pk),
        )
        self.assertEqual(search.status_code, 200, search.content)
        self.assertTrue(len(search.json()["data"]["items"]) >= 1)

        walk = self.client.post(
            reverse("api:walk_in"),
            data='{"room_id":%d,"first_name":"Bob","nights":1,"allow_no_docs":true}'
            % room2.pk,
            **headers,
        )
        # room2 walk-in — room 101 still has confirmed reservation
        # Actually room2 is free. But self.room has confirmed reservation occupying it.
        self.assertEqual(walk.status_code, 201, walk.content)
        rid = walk.json()["data"]["reservation_id"]

        extend = self.client.post(
            reverse("api:reservation_extend", kwargs={"pk": rid}),
            data='{"nights":1}',
            **headers,
        )
        self.assertEqual(extend.status_code, 200, extend.content)
        self.assertEqual(
            extend.json()["data"]["check_out"],
            (self.today + timedelta(days=2)).isoformat(),
        )

        # Transfer Bob from 102 to a third room
        room3 = Room.objects.create(
            tenant=self.tenant, property=self.prop, room_type=self.rt, number="103"
        )
        xfer = self.client.post(
            reverse("api:reservation_transfer", kwargs={"pk": rid}),
            data='{"room_id":%d}' % room3.pk,
            **headers,
        )
        self.assertEqual(xfer.status_code, 200, xfer.content)
        self.assertEqual(xfer.json()["data"]["room"]["number"], "103")

    def test_create_cancel_and_available(self):
        token = self._login()
        headers = {
            "HTTP_AUTHORIZATION": f"Bearer {token}",
            "HTTP_X_HOTEL_ID": str(self.prop.pk),
            "content_type": "application/json",
        }
        check_in = self.today + timedelta(days=3)
        check_out = check_in + timedelta(days=2)
        avail = self.client.get(
            reverse("api:rooms_available")
            + f"?check_in={check_in.isoformat()}&check_out={check_out.isoformat()}",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_HOTEL_ID=str(self.prop.pk),
        )
        self.assertEqual(avail.status_code, 200, avail.content)
        self.assertTrue(
            any(i["id"] == self.room.pk for i in avail.json()["data"]["items"])
        )

        create = self.client.post(
            reverse("api:reservation_create"),
            data=(
                '{"room_id":%d,"first_name":"Nodira","check_in":"%s","check_out":"%s","adults":1}'
                % (self.room.pk, check_in.isoformat(), check_out.isoformat())
            ),
            **headers,
        )
        self.assertEqual(create.status_code, 201, create.content)
        rid = create.json()["data"]["reservation_id"]
        self.assertEqual(create.json()["data"]["status"], "confirmed")

        cancel = self.client.post(
            reverse("api:reservation_cancel", kwargs={"pk": rid}),
            data='{"reason":"test"}',
            **headers,
        )
        self.assertEqual(cancel.status_code, 200, cancel.content)
        self.assertEqual(cancel.json()["data"]["status"], "cancelled")

    def test_cash_shift_and_notes(self):
        token = self._login()
        headers = {
            "HTTP_AUTHORIZATION": f"Bearer {token}",
            "HTTP_X_HOTEL_ID": str(self.prop.pk),
            "content_type": "application/json",
        }
        status = self.client.get(
            reverse("api:cash_shift_status"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_HOTEL_ID=str(self.prop.pk),
        )
        self.assertEqual(status.status_code, 200, status.content)
        self.assertIsNone(status.json()["data"]["shift"])

        opened = self.client.post(
            reverse("api:cash_shift_open"),
            data='{"opening_float":"100000"}',
            **headers,
        )
        self.assertEqual(opened.status_code, 201, opened.content)
        self.assertTrue(opened.json()["data"]["shift"]["is_open"])

        walk = self.client.post(
            reverse("api:walk_in"),
            data='{"room_id":%d,"first_name":"Cash","nights":1,"allow_no_docs":true}'
            % self.room.pk,
            **headers,
        )
        self.assertEqual(walk.status_code, 201, walk.content)
        rid = walk.json()["data"]["reservation_id"]

        notes = self.client.post(
            reverse("api:reservation_notes", kwargs={"pk": rid}),
            data='{"notes":"VIP mehmon"}',
            **headers,
        )
        self.assertEqual(notes.status_code, 200, notes.content)
        self.assertEqual(notes.json()["data"]["notes"], "VIP mehmon")

        detail = self.client.get(
            reverse("api:reservation_detail", kwargs={"pk": rid}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_HOTEL_ID=str(self.prop.pk),
        )
        self.assertEqual(detail.json()["data"]["notes"], "VIP mehmon")

        closed = self.client.post(
            reverse("api:cash_shift_close"),
            data='{"closing_cash":"100000"}',
            **headers,
        )
        self.assertEqual(closed.status_code, 200, closed.content)
        self.assertFalse(closed.json()["data"]["shift"]["is_open"])

    def test_deposit_minibar_guests_hk(self):
        from inventory.models import StockItem

        token = self._login()
        headers = {
            "HTTP_AUTHORIZATION": f"Bearer {token}",
            "HTTP_X_HOTEL_ID": str(self.prop.pk),
            "content_type": "application/json",
        }
        # Open cash for later cash ops if needed — deposit via card
        create = self.client.post(
            reverse("api:reservation_create"),
            data=(
                '{"room_id":%d,"first_name":"Deposit","check_in":"%s","check_out":"%s"}'
                % (
                    self.room.pk,
                    (self.today + timedelta(days=5)).isoformat(),
                    (self.today + timedelta(days=7)).isoformat(),
                )
            ),
            **headers,
        )
        self.assertEqual(create.status_code, 201, create.content)
        rid = create.json()["data"]["reservation_id"]

        dep = self.client.post(
            reverse("api:reservation_deposit", kwargs={"pk": rid}),
            data='{"amount":"200000","method":"card"}',
            **headers,
        )
        self.assertEqual(dep.status_code, 201, dep.content)

        walk = self.client.post(
            reverse("api:walk_in"),
            data='{"room_id":%d,"first_name":"Mini","nights":1,"allow_no_docs":true}'
            % Room.objects.create(
                tenant=self.tenant,
                property=self.prop,
                room_type=self.rt,
                number="201",
            ).pk,
            **headers,
        )
        self.assertEqual(walk.status_code, 201, walk.content)
        wid = walk.json()["data"]["reservation_id"]

        item = StockItem.objects.create(
            tenant=self.tenant,
            hotel=self.prop,
            name="Cola",
            sku="cola",
            sell_price=Decimal("15000"),
            quantity_on_hand=Decimal("10"),
            is_minibar=True,
            is_active=True,
        )
        mb = self.client.post(
            reverse("api:reservation_minibar", kwargs={"pk": wid}),
            data='{"item_id":%d,"quantity":"1"}' % item.pk,
            **headers,
        )
        self.assertEqual(mb.status_code, 201, mb.content)

        guests = self.client.get(
            reverse("api:guest_list") + "?q=Mini",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_HOTEL_ID=str(self.prop.pk),
        )
        self.assertEqual(guests.status_code, 200)
        self.assertTrue(len(guests.json()["data"]["items"]) >= 1)

        hk = self.client.get(
            reverse("api:housekeeping_board"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_HOTEL_ID=str(self.prop.pk),
        )
        self.assertEqual(hk.status_code, 200, hk.content)
        self.assertIn("stats", hk.json()["data"])

    def test_calendar_flash_maintenance_void(self):
        token = self._login()
        headers = {
            "HTTP_AUTHORIZATION": f"Bearer {token}",
            "HTTP_X_HOTEL_ID": str(self.prop.pk),
            "content_type": "application/json",
        }

        cal = self.client.get(
            reverse("api:calendar") + "?days=14",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_HOTEL_ID=str(self.prop.pk),
        )
        self.assertEqual(cal.status_code, 200, cal.content)
        self.assertIn("rows", cal.json()["data"])
        self.assertEqual(cal.json()["data"]["days_count"], 14)

        flash = self.client.get(
            reverse("api:flash_report"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_HOTEL_ID=str(self.prop.pk),
        )
        self.assertEqual(flash.status_code, 200, flash.content)
        self.assertIn("flash", flash.json()["data"])
        self.assertIn("kpis", flash.json()["data"])

        maint = self.client.post(
            reverse("api:maintenance_create"),
            data='{"title":"Konditsioner","priority":"high","room_id":%d}'
            % self.room.pk,
            **headers,
        )
        self.assertEqual(maint.status_code, 201, maint.content)
        tid = maint.json()["data"]["id"]

        listed = self.client.get(
            reverse("api:maintenance_list"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_HOTEL_ID=str(self.prop.pk),
        )
        self.assertEqual(listed.status_code, 200, listed.content)
        self.assertTrue(
            any(t["id"] == tid for t in listed.json()["data"]["items"])
        )

        done = self.client.post(
            reverse("api:maintenance_complete", kwargs={"pk": tid}),
            data="{}",
            **headers,
        )
        self.assertEqual(done.status_code, 200, done.content)
        self.assertEqual(done.json()["data"]["status"], "done")

        # Void requires accountant/admin — receptionist gets 403
        walk = self.client.post(
            reverse("api:walk_in"),
            data='{"room_id":%d,"first_name":"Void","nights":1,"allow_no_docs":true}'
            % Room.objects.create(
                tenant=self.tenant,
                property=self.prop,
                room_type=self.rt,
                number="301",
            ).pk,
            **headers,
        )
        self.assertEqual(walk.status_code, 201, walk.content)
        rid = walk.json()["data"]["reservation_id"]

        charge = self.client.post(
            reverse("api:reservation_charge", kwargs={"pk": rid}),
            data='{"description":"Extra","unit_price":"10000","quantity":"1"}',
            **headers,
        )
        self.assertEqual(charge.status_code, 201, charge.content)
        cid = charge.json()["data"]["charge_id"]

        void_denied = self.client.post(
            reverse("api:void_charge", kwargs={"pk": cid}),
            data='{"reason":"test"}',
            **headers,
        )
        self.assertEqual(void_denied.status_code, 403)

        TenantMembership.objects.filter(user=self.user, tenant=self.tenant).update(
            role=TenantMembership.Role.ADMIN
        )
        void_ok = self.client.post(
            reverse("api:void_charge", kwargs={"pk": cid}),
            data='{"reason":"test void"}',
            **headers,
        )
        self.assertEqual(void_ok.status_code, 200, void_ok.content)
        self.assertTrue(void_ok.json()["data"]["is_void"])

    def test_guest_update_and_companies(self):
        token = self._login()
        headers = {
            "content_type": "application/json",
            "HTTP_AUTHORIZATION": f"Bearer {token}",
            "HTTP_X_HOTEL_ID": str(self.prop.pk),
        }
        detail = self.client.get(
            reverse("api:guest_detail", kwargs={"pk": self.guest.pk}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_HOTEL_ID=str(self.prop.pk),
        )
        self.assertEqual(detail.status_code, 200, detail.content)
        self.assertEqual(detail.json()["data"]["first_name"], "Ali")

        updated = self.client.post(
            reverse("api:guest_detail", kwargs={"pk": self.guest.pk}),
            data='{"phone":"+998901112233","notes":"VIP"}',
            **headers,
        )
        self.assertEqual(updated.status_code, 200, updated.content)
        self.assertEqual(updated.json()["data"]["phone"], "+998901112233")

        doc = self.client.post(
            reverse("api:guest_add_document", kwargs={"pk": self.guest.pk}),
            data='{"number":"AA1234567","doc_type":"passport"}',
            **headers,
        )
        self.assertEqual(doc.status_code, 201, doc.content)

        company = self.client.post(
            reverse("api:company_create"),
            data='{"name":"Acme LLC","phone":"712000000"}',
            **headers,
        )
        self.assertEqual(company.status_code, 201, company.content)

        companies = self.client.get(
            reverse("api:companies"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_HOTEL_ID=str(self.prop.pk),
        )
        self.assertEqual(companies.status_code, 200, companies.content)
        self.assertTrue(
            any(
                c["name"] == "Acme LLC"
                for c in companies.json()["data"]["items"]
            )
        )

        ledger = self.client.get(
            reverse("api:city_ledger"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_HOTEL_ID=str(self.prop.pk),
        )
        self.assertEqual(ledger.status_code, 200, ledger.content)
        self.assertIn("items", ledger.json()["data"])

        groups = self.client.get(
            reverse("api:groups"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_HOTEL_ID=str(self.prop.pk),
        )
        self.assertEqual(groups.status_code, 200, groups.content)
        self.assertIn("items", groups.json()["data"])

        expenses = self.client.get(
            reverse("api:expenses"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_HOTEL_ID=str(self.prop.pk),
        )
        # receptionist may be denied finance — accept 200 or 403
        self.assertIn(expenses.status_code, (200, 403), expenses.content)

        audit = self.client.get(
            reverse("api:night_audit_status"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_HOTEL_ID=str(self.prop.pk),
        )
        self.assertIn(audit.status_code, (200, 403), audit.content)

    def test_inventory_and_referrers(self):
        from inventory.models import StockItem

        token = self._login()
        headers = {
            "content_type": "application/json",
            "HTTP_AUTHORIZATION": f"Bearer {token}",
            "HTTP_X_HOTEL_ID": str(self.prop.pk),
        }
        item = StockItem.objects.create(
            tenant=self.tenant,
            hotel=self.prop,
            name="Suv",
            sku="suv-05",
            quantity_on_hand=Decimal("5"),
            reorder_level=Decimal("10"),
            unit_cost=Decimal("2000"),
            sell_price=Decimal("5000"),
            is_minibar=True,
        )
        listed = self.client.get(
            reverse("api:inventory_items"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_HOTEL_ID=str(self.prop.pk),
        )
        self.assertEqual(listed.status_code, 200, listed.content)
        self.assertTrue(
            any(i["id"] == item.pk for i in listed.json()["data"]["items"])
        )

        adj = self.client.post(
            reverse("api:inventory_adjust", kwargs={"pk": item.pk}),
            data='{"movement_type":"in","quantity":"5"}',
            **headers,
        )
        self.assertEqual(adj.status_code, 200, adj.content)
        self.assertEqual(adj.json()["data"]["quantity_on_hand"], "10.00")

        ref = self.client.post(
            reverse("api:referrer_create"),
            data='{"name":"Agent One","default_commission_percent":"10"}',
            **headers,
        )
        self.assertEqual(ref.status_code, 201, ref.content)

        refs = self.client.get(
            reverse("api:referrers"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_HOTEL_ID=str(self.prop.pk),
        )
        self.assertEqual(refs.status_code, 200, refs.content)
        self.assertTrue(
            any(r["name"] == "Agent One" for r in refs.json()["data"]["items"])
        )

        # HR denied for receptionist
        hr = self.client.get(
            reverse("api:hr_employees"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_HOTEL_ID=str(self.prop.pk),
        )
        self.assertEqual(hr.status_code, 403)
