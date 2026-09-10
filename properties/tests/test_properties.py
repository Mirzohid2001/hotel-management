from datetime import date, timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse

from core.tests.helpers import setup_tenant_user
from properties.models import Floor, Property, RatePlan, Room, RoomType, SeasonRate
from properties.services import quote_stay
from subscriptions.models import Plan


class PropertyModelTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(username="propowner")

    def test_create_property_room_and_quote(self):
        prop = Property.objects.create(tenant=self.ctx["tenant"], name="Aida")
        rt = RoomType.objects.create(
            tenant=self.ctx["tenant"],
            property=prop,
            name="Standard",
            code="std",
            base_price=Decimal("500000"),
        )
        Room.objects.create(
            tenant=self.ctx["tenant"],
            property=prop,
            room_type=rt,
            number="101",
        )
        rate = RatePlan.objects.create(
            tenant=self.ctx["tenant"],
            property=prop,
            room_type=rt,
            name="BAR",
            code="bar",
            price=Decimal("400000"),
            is_default=True,
        )
        SeasonRate.objects.create(
            tenant=self.ctx["tenant"],
            rate_plan=rate,
            name="Summer",
            date_from=date(2026, 6, 1),
            date_to=date(2026, 8, 31),
            price=Decimal("550000"),
        )
        total = quote_stay(rate, date(2026, 6, 10), date(2026, 6, 12), adults=1)
        self.assertEqual(total, Decimal("1100000"))

    def test_free_plan_room_limit_on_create_view(self):
        ctx = setup_tenant_user(plan_code=Plan.Code.FREE, username="freeroom")
        prop = Property.objects.create(tenant=ctx["tenant"], name="Small")
        rt = RoomType.objects.create(
            tenant=ctx["tenant"], property=prop, name="Std", code="s", base_price=1
        )
        for i in range(10):
            Room.objects.create(
                tenant=ctx["tenant"], property=prop, room_type=rt, number=str(100 + i)
            )
        client = Client()
        client.login(username="freeroom", password="pass12345")
        response = client.get(reverse("properties:room_create", args=[prop.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(prop.rooms.count(), 10)

    def test_quick_room_type_and_floor_from_room_form(self):
        prop = Property.objects.create(tenant=self.ctx["tenant"], name="Quick Hotel")
        client = Client()
        client.login(username="propowner", password="pass12345")

        room_page = client.get(reverse("properties:room_create", args=[prop.pk]))
        self.assertEqual(room_page.status_code, 200)
        self.assertContains(room_page, "room-types/quick")
        self.assertContains(room_page, "floors/quick")

        rt_resp = client.post(
            reverse("properties:room_type_quick", args=[prop.pk]),
            {
                "name": "Lyuks",
                "code": "",
                "base_price": "750000",
                "capacity_adults": "2",
                "select_id": "id_room_type",
                "field_name": "room_type",
            },
        )
        self.assertEqual(rt_resp.status_code, 200)
        self.assertTrue(RoomType.objects.filter(property=prop, name="Lyuks").exists())
        self.assertContains(rt_resp, "id_room_type")

        fl_resp = client.post(
            reverse("properties:floor_quick", args=[prop.pk]),
            {
                "number": "3",
                "name": "Uchinchi",
                "select_id": "id_floor",
                "field_name": "floor",
            },
        )
        self.assertEqual(fl_resp.status_code, 200)
        self.assertTrue(
            Floor.objects.filter(property=prop, number=3, name="Uchinchi").exists()
        )
        self.assertContains(fl_resp, "id_floor")

    def test_room_and_room_type_edit(self):
        prop = Property.objects.create(tenant=self.ctx["tenant"], name="Edit Hotel")
        rt = RoomType.objects.create(
            tenant=self.ctx["tenant"],
            property=prop,
            name="Std",
            code="std",
            base_price=Decimal("100000"),
        )
        room = Room.objects.create(
            tenant=self.ctx["tenant"],
            property=prop,
            room_type=rt,
            number="101",
        )
        client = Client()
        client.login(username="propowner", password="pass12345")

        resp = client.post(
            reverse("properties:room_type_edit", args=[prop.pk, rt.pk]),
            {
                "name": "Deluxe",
                "code": "std",
                "capacity_adults": "2",
                "capacity_children": "0",
                "base_price": "150000",
                "currency": "UZS",
                "description": "",
                "is_active": "on",
            },
        )
        self.assertEqual(resp.status_code, 302)
        rt.refresh_from_db()
        self.assertEqual(rt.name, "Deluxe")
        self.assertEqual(rt.base_price, Decimal("150000"))

        resp = client.post(
            reverse("properties:room_edit", args=[prop.pk, room.pk]),
            {
                "room_type": rt.pk,
                "floor": "",
                "number": "102",
                "status": "ready",
                "notes": "Renovated",
                "is_active": "on",
            },
        )
        self.assertEqual(resp.status_code, 302)
        room.refresh_from_db()
        self.assertEqual(room.number, "102")
        self.assertEqual(room.notes, "Renovated")

    def test_seed_standard_room_types(self):
        prop = Property.objects.create(tenant=self.ctx["tenant"], name="Preset Hotel")
        client = Client()
        client.login(username="propowner", password="pass12345")

        detail = client.get(reverse("properties:detail", args=[prop.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "room-types/seed")
        self.assertContains(detail, "Twin")
        self.assertContains(detail, "Double")
        self.assertContains(detail, "Triple")

        resp = client.post(
            reverse("properties:room_types_seed", args=[prop.pk]),
            {"base_price": "500000", "with_rates": "1"},
        )
        self.assertEqual(resp.status_code, 302)
        codes = set(
            RoomType.objects.filter(property=prop, is_active=True).values_list("code", flat=True)
        )
        self.assertEqual(codes, {"twin", "double", "triple"})
        twin = RoomType.objects.get(property=prop, code="twin")
        self.assertEqual(twin.base_price, Decimal("500000"))
        self.assertEqual(twin.capacity_adults, 2)
        triple = RoomType.objects.get(property=prop, code="triple")
        self.assertEqual(triple.base_price, Decimal("675000"))
        self.assertTrue(
            RatePlan.objects.filter(property=prop, room_type=triple, is_default=True).exists()
        )

        # Ikkinchi chaqiriq — yangi tur yaratmasin
        before = RoomType.objects.filter(property=prop, is_active=True).count()
        resp2 = client.post(
            reverse("properties:room_types_seed", args=[prop.pk]),
            {"base_price": "600000", "with_rates": "1"},
        )
        self.assertEqual(resp2.status_code, 302)
        self.assertEqual(RoomType.objects.filter(property=prop, is_active=True).count(), before)
        twin.refresh_from_db()
        self.assertEqual(twin.base_price, Decimal("500000"))

        # Bitta kod bo‘lsa — faqat qolganlari; ortiqcha turlar o‘chiriladi
        prop2 = Property.objects.create(tenant=self.ctx["tenant"], name="Partial Hotel")
        RoomType.objects.create(
            tenant=self.ctx["tenant"],
            property=prop2,
            name="Custom Double",
            code="double",
            base_price=Decimal("400000"),
        )
        RoomType.objects.create(
            tenant=self.ctx["tenant"],
            property=prop2,
            name="Old Suite",
            code="suite",
            base_price=Decimal("900000"),
        )
        client.post(
            reverse("properties:room_types_seed", args=[prop2.pk]),
            {"base_price": "500000"},
        )
        self.assertEqual(
            set(
                RoomType.objects.filter(property=prop2, is_active=True).values_list(
                    "code", flat=True
                )
            ),
            {"twin", "double", "triple"},
        )
        self.assertEqual(
            RoomType.objects.get(property=prop2, code="double").name, "Custom Double"
        )
        self.assertFalse(RoomType.objects.get(property=prop2, code="suite").is_active)

    def test_floor_and_rate_edit_delete(self):
        prop = Property.objects.create(tenant=self.ctx["tenant"], name="Edit Hotel")
        floor = Floor.objects.create(
            tenant=self.ctx["tenant"], property=prop, number=1, name="Birinchi"
        )
        rt = RoomType.objects.create(
            tenant=self.ctx["tenant"],
            property=prop,
            name="Double",
            code="double",
            base_price=Decimal("500000"),
        )
        rate = RatePlan.objects.create(
            tenant=self.ctx["tenant"],
            property=prop,
            room_type=rt,
            name="BAR",
            code="bar-double",
            price=Decimal("500000"),
        )
        client = Client()
        client.login(username="propowner", password="pass12345")

        detail = client.get(reverse("properties:detail", args=[prop.pk]))
        self.assertContains(detail, reverse("properties:floor_edit", args=[prop.pk, floor.pk]))
        self.assertContains(detail, reverse("properties:floor_delete", args=[prop.pk, floor.pk]))
        self.assertContains(detail, reverse("properties:rate_plan_edit", args=[prop.pk, rate.pk]))
        self.assertContains(detail, reverse("properties:rate_plan_delete", args=[prop.pk, rate.pk]))

        edit = client.post(
            reverse("properties:floor_edit", args=[prop.pk, floor.pk]),
            {"number": "2", "name": "Ikkinchi"},
        )
        self.assertEqual(edit.status_code, 302)
        floor.refresh_from_db()
        self.assertEqual(floor.number, 2)
        self.assertEqual(floor.name, "Ikkinchi")

        rate_edit = client.post(
            reverse("properties:rate_plan_edit", args=[prop.pk, rate.pk]),
            {
                "name": "BAR Plus",
                "code": "bar-double",
                "room_type": rt.pk,
                "price": "550000",
                "extra_adult_price": "0",
                "currency": "UZS",
                "is_default": "on",
                "is_active": "on",
            },
        )
        self.assertEqual(rate_edit.status_code, 302)
        rate.refresh_from_db()
        self.assertEqual(rate.name, "BAR Plus")
        self.assertEqual(rate.price, Decimal("550000"))

        Room.objects.create(
            tenant=self.ctx["tenant"],
            property=prop,
            room_type=rt,
            floor=floor,
            number="201",
        )
        del_floor = client.post(reverse("properties:floor_delete", args=[prop.pk, floor.pk]))
        self.assertEqual(del_floor.status_code, 302)
        self.assertFalse(Floor.objects.filter(pk=floor.pk).exists())
        self.assertIsNone(Room.objects.get(number="201", property=prop).floor_id)

        del_rate = client.post(reverse("properties:rate_plan_delete", args=[prop.pk, rate.pk]))
        self.assertEqual(del_rate.status_code, 302)
        self.assertFalse(RatePlan.objects.filter(pk=rate.pk).exists())

    def test_room_and_room_type_delete(self):
        prop = Property.objects.create(tenant=self.ctx["tenant"], name="Delete Hotel")
        rt = RoomType.objects.create(
            tenant=self.ctx["tenant"],
            property=prop,
            name="Orphan Type",
            code="orphan",
            base_price=Decimal("100000"),
        )
        rt_keep = RoomType.objects.create(
            tenant=self.ctx["tenant"],
            property=prop,
            name="Keep",
            code="keep",
            base_price=Decimal("200000"),
        )
        room = Room.objects.create(
            tenant=self.ctx["tenant"],
            property=prop,
            room_type=rt_keep,
            number="301",
        )
        RatePlan.objects.create(
            tenant=self.ctx["tenant"],
            property=prop,
            room_type=rt,
            name="Orphan BAR",
            code="bar-orphan",
            price=Decimal("100000"),
        )
        client = Client()
        client.login(username="propowner", password="pass12345")

        detail = client.get(reverse("properties:detail", args=[prop.pk]))
        self.assertContains(detail, reverse("properties:room_type_delete", args=[prop.pk, rt.pk]))
        self.assertContains(detail, reverse("properties:room_delete", args=[prop.pk, room.pk]))

        blocked = client.post(reverse("properties:room_type_delete", args=[prop.pk, rt_keep.pk]))
        self.assertEqual(blocked.status_code, 302)
        self.assertTrue(RoomType.objects.filter(pk=rt_keep.pk).exists())

        ok_type = client.post(reverse("properties:room_type_delete", args=[prop.pk, rt.pk]))
        self.assertEqual(ok_type.status_code, 302)
        self.assertFalse(RoomType.objects.filter(pk=rt.pk).exists())
        self.assertFalse(RatePlan.objects.filter(code="bar-orphan", property=prop).exists())

        ok_room = client.post(reverse("properties:room_delete", args=[prop.pk, room.pk]))
        self.assertEqual(ok_room.status_code, 302)
        self.assertFalse(Room.objects.filter(pk=room.pk).exists())


class GuestViewTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(username="guestowner")
        self.client = Client()
        self.client.login(username="guestowner", password="pass12345")

    def test_create_and_search_guest(self):
        response = self.client.post(
            reverse("guests:create"),
            {
                "first_name": "Ali",
                "last_name": "Valiyev",
                "phone": "+998901112233",
                "email": "",
                "nationality": "UZ",
                "company": "",
                "blacklist_reason": "",
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        list_resp = self.client.get(reverse("guests:list"), {"q": "Ali"})
        self.assertContains(list_resp, "Ali Valiyev")
