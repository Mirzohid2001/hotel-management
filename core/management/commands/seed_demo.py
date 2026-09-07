from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from bookings.models import BookingReferrer, Reservation
from bookings.services import check_in_reservation, create_reservation
from finance.models import Expense, ExpenseCategory, Vendor
from finance.services import approve_expense, mark_expense_paid
from folio.models import GuestPayment
from folio.services import add_payment, ensure_stay_nights_posted, get_open_shift, open_cash_shift
from guests.models import Company, Guest, GuestDocument
from hr.models import Employee
from housekeeping.models import HousekeepingTask
from inventory.models import StockItem
from properties.models import Floor, Property, PropertySettings, RatePlan, Room, RoomType
from properties.services import seed_standard_room_types
from services.models import ServiceItem
from subscriptions.models import Plan, Subscription
from tenants.models import Tenant, TenantMembership


class Command(BaseCommand):
    help = "Seed demo tenant, ideal room types, rooms, guests (password: demo12345)"

    def handle(self, *args, **options):
        from django.core.management import call_command

        call_command("seed_plans")
        plan = Plan.objects.get(code=Plan.Code.PRO)
        tenant, _ = Tenant.objects.get_or_create(
            slug="rivoj-hotel", defaults={"name": "Rivoj Hotel"}
        )
        today = timezone.localdate()
        Subscription.objects.update_or_create(
            tenant=tenant,
            defaults={
                "plan": plan,
                "period_start": today - timedelta(days=1),
                "period_end": today + timedelta(days=365),
                "status": Subscription.Status.ACTIVE,
                "billing_period": Subscription.BillingPeriod.YEARLY,
                "admin_notes": "Demo seed",
            },
        )
        user, created = User.objects.get_or_create(
            username="demo",
            defaults={
                "first_name": "Demo",
                "last_name": "Owner",
                "email": "demo@hotel.local",
            },
        )
        if created:
            user.set_password("demo12345")
            user.save()
        TenantMembership.objects.update_or_create(
            user=user,
            tenant=tenant,
            defaults={"role": TenantMembership.Role.ADMIN, "is_active": True},
        )

        manager, mgr_created = User.objects.get_or_create(
            username="manager",
            defaults={
                "first_name": "Dilshod",
                "last_name": "Manager",
                "email": "manager@hotel.local",
            },
        )
        if mgr_created:
            manager.set_password("demo12345")
            manager.save()
        TenantMembership.objects.update_or_create(
            user=manager,
            tenant=tenant,
            defaults={"role": TenantMembership.Role.MANAGER, "is_active": True},
        )

        for su in User.objects.filter(is_superuser=True):
            TenantMembership.objects.update_or_create(
                user=su,
                tenant=tenant,
                defaults={"role": TenantMembership.Role.ADMIN, "is_active": True},
            )

        prop, _ = Property.objects.get_or_create(
            tenant=tenant,
            name="Rivoj Hotel",
            defaults={
                "city": "Toshkent",
                "address": "Amir Temur ko‘chasi 12",
                "branch_code": "tsh",
                "phone": "+998712000000",
            },
        )
        PropertySettings.objects.update_or_create(
            tenant=tenant,
            property=prop,
            defaults={
                "tax_percent": "12",
                "require_id_on_checkin": True,
                "emehmon_fee": Decimal("9000"),
            },
        )

        from tenants.models import ExchangeRate
        from django.utils import timezone as tz

        today = tz.localdate()
        for code, rate in (("USD", Decimal("12700")), ("EUR", Decimal("13800"))):
            ExchangeRate.objects.update_or_create(
                tenant=tenant,
                currency=code,
                base_currency="UZS",
                effective_on=today,
                defaults={"rate": rate, "note": "Demo kurs"},
            )

        # —— Ideal xona turlari + BAR tariflar ——
        seed_result = seed_standard_room_types(
            tenant=tenant,
            prop=prop,
            base_price=Decimal("500000"),
            with_rate_plans=True,
        )
        self.stdout.write(
            f"Room types: +{len(seed_result['created_types'])} "
            f"(skipped {seed_result['skipped']}), rates +{len(seed_result['created_rates'])}"
        )

        types = {rt.code: rt for rt in RoomType.objects.filter(property=prop)}
        rates = {
            rp.room_type_id: rp
            for rp in RatePlan.objects.filter(property=prop, is_default=True)
        }

        # Eski "std" turi — xona bog‘lanmagan bo‘lsa o‘chirish (faolsiz)
        legacy_std = types.get("std")
        if legacy_std and not legacy_std.rooms.exists():
            legacy_std.is_active = False
            legacy_std.save(update_fields=["is_active"])
            RatePlan.objects.filter(property=prop, room_type=legacy_std).update(is_active=False)

        rt_double = types.get("double") or types.get("twin") or next(iter(types.values()))
        rate_double = rates.get(rt_double.id) or RatePlan.objects.filter(
            property=prop, room_type=rt_double
        ).first()

        floors = {}
        for num, name in ((1, "Birinchi"), (2, "Ikkinchi"), (3, "Uchinchi")):
            fl, _ = Floor.objects.get_or_create(
                tenant=tenant,
                property=prop,
                number=num,
                defaults={"name": name},
            )
            floors[num] = fl

        # Xonalar: qavat + tur
        room_plan = [
            ("101", "twin", 1),
            ("102", "twin", 1),
            ("103", "double", 1),
            ("104", "double", 1),
            ("201", "twin", 2),
            ("202", "double", 2),
            ("203", "triple", 2),
            ("301", "double", 3),
            ("302", "triple", 3),
            ("303", "double", 3),
        ]
        rooms = {}
        for number, type_code, floor_num in room_plan:
            rt = types.get(type_code) or rt_double
            room, created_room = Room.objects.get_or_create(
                tenant=tenant,
                property=prop,
                number=number,
                defaults={"room_type": rt, "floor": floors[floor_num], "status": Room.Status.READY},
            )
            if not created_room:
                changed = False
                if room.room_type_id != rt.id:
                    room.room_type = rt
                    changed = True
                if room.floor_id != floors[floor_num].id:
                    room.floor = floors[floor_num]
                    changed = True
                if changed:
                    room.save()
            rooms[number] = room

        company, _ = Company.objects.get_or_create(
            tenant=tenant,
            name="Rivoj Travel LLC",
            defaults={"phone": "+998711112233", "inn": "123456789"},
        )
        referrer, _ = BookingReferrer.objects.get_or_create(
            tenant=tenant,
            name="Booking Partner",
            defaults={"default_commission_percent": Decimal("10"), "phone": "+998901110011"},
        )

        guest, _ = Guest.objects.get_or_create(
            tenant=tenant,
            first_name="Sardor",
            last_name="Aliyev",
            defaults={"phone": "+998901234567", "is_vip": True},
        )
        GuestDocument.objects.get_or_create(
            tenant=tenant,
            guest=guest,
            defaults={
                "doc_type": GuestDocument.DocType.PASSPORT,
                "number": "AA1234567",
            },
        )
        guest_b, _ = Guest.objects.get_or_create(
            tenant=tenant,
            first_name="Malika",
            last_name="Karimova",
            defaults={"phone": "+998907654321"},
        )
        GuestDocument.objects.get_or_create(
            tenant=tenant,
            guest=guest_b,
            defaults={
                "doc_type": GuestDocument.DocType.ID_CARD,
                "number": "AD9988776",
            },
        )
        Guest.objects.get_or_create(
            tenant=tenant,
            first_name="Jasur",
            last_name="Rahimov",
            defaults={"phone": "+998935551122", "company": company},
        )
        Guest.objects.get_or_create(
            tenant=tenant,
            first_name="Nilufar",
            last_name="Sobirova",
            defaults={"phone": "+998944443322", "is_vip": True},
        )

        cat_kommunal, _ = ExpenseCategory.objects.get_or_create(tenant=tenant, name="Kommunal")
        cat_food, _ = ExpenseCategory.objects.get_or_create(tenant=tenant, name="Oziq-ovqat")
        cat_repair, _ = ExpenseCategory.objects.get_or_create(tenant=tenant, name="Ta’mirlash")
        vendor_util, _ = Vendor.objects.get_or_create(
            tenant=tenant, name="Kommunal xizmat", defaults={"phone": "+998712345678"}
        )
        vendor_food, _ = Vendor.objects.get_or_create(
            tenant=tenant, name="Oziq-ovqat yetkazuvchi", defaults={"phone": "+998712345679"}
        )

        Employee.objects.get_or_create(
            tenant=tenant,
            full_name="Dilnoza Reception",
            defaults={"position": "Receptionist", "base_salary": Decimal("3000000")},
        )
        Employee.objects.get_or_create(
            tenant=tenant,
            full_name="Aziz Housekeeping",
            defaults={"position": "Housekeeper", "base_salary": Decimal("2500000")},
        )
        Employee.objects.get_or_create(
            tenant=tenant,
            full_name="Bobur Accountant",
            defaults={"position": "Accountant", "base_salary": Decimal("4500000")},
        )

        for code, name, price in (
            ("breakfast", "Nonushta", "75000"),
            ("laundry", "Kir yuvish", "45000"),
            ("transfer", "Aeroport transfer", "150000"),
            ("spa", "SPA 1 soat", "200000"),
        ):
            ServiceItem.objects.get_or_create(
                tenant=tenant,
                code=code,
                defaults={"name": name, "unit_price": Decimal(price)},
            )

        for sku, name, qty, sell, cost, minibar in (
            ("cola", "Cola 0.5", "48", "15000", "8000", True),
            ("water", "Suv 0.5", "60", "8000", "3500", True),
            ("snickers", "Snickers", "36", "12000", "7000", True),
            ("towel", "Sochiq (zaxira)", "80", "0", "25000", False),
            ("shampoo", "Shampoo 30ml", "100", "0", "5000", False),
        ):
            StockItem.objects.get_or_create(
                tenant=tenant,
                hotel=prop,
                sku=sku,
                defaults={
                    "name": name,
                    "quantity_on_hand": Decimal(qty),
                    "sell_price": Decimal(sell),
                    "unit_cost": Decimal(cost),
                    "is_minibar": minibar,
                    "reorder_level": Decimal("10"),
                },
            )

        if not get_open_shift(tenant, hotel=prop):
            open_cash_shift(tenant, user, Decimal("500000"), hotel=prop)
            self.stdout.write("Demo cash shift opened.")

        # In-house: Double 103
        if not Reservation.objects.filter(tenant=tenant, room=rooms["103"]).exists():
            reservation = create_reservation(
                tenant=tenant,
                user=user,
                property_obj=prop,
                guest=guest,
                room_type=rooms["103"].room_type,
                room=rooms["103"],
                rate_plan=rates.get(rooms["103"].room_type_id) or rate_double,
                check_in=today,
                check_out=today + timedelta(days=2),
                source=Reservation.Source.WALKIN,
                notes="Demo check-in · Double",
                adults=2,
                referrer=referrer,
                commission_percent=Decimal("10"),
            )
            check_in_reservation(reservation, user)
            ensure_stay_nights_posted(reservation, user)
            folio = reservation.folio
            if folio.balance > 0:
                add_payment(
                    folio,
                    user,
                    amount=min(folio.balance, Decimal("200000")),
                    method=GuestPayment.Method.CASH,
                    note="Demo depozit",
                )
            self.stdout.write(f"Demo reservation: {reservation.code}")

        # Kelajak bron: Twin 102
        if not Reservation.objects.filter(tenant=tenant, room=rooms["102"]).exists():
            confirmed = create_reservation(
                tenant=tenant,
                user=user,
                property_obj=prop,
                guest=guest_b,
                room_type=rooms["102"].room_type,
                room=rooms["102"],
                rate_plan=rates.get(rooms["102"].room_type_id) or rate_double,
                check_in=today + timedelta(days=1),
                check_out=today + timedelta(days=3),
                source=Reservation.Source.PHONE,
                notes="Demo confirmed · Twin",
                status=Reservation.Status.CONFIRMED,
                adults=2,
            )
            self.stdout.write(f"Demo confirmed: {confirmed.code}")

        # Suite inquiry
        if not Reservation.objects.filter(tenant=tenant, room=rooms["301"]).exists():
            inquiry = create_reservation(
                tenant=tenant,
                user=user,
                property_obj=prop,
                guest=guest,
                room_type=rooms["301"].room_type,
                room=rooms["301"],
                rate_plan=rates.get(rooms["301"].room_type_id) or rate_double,
                check_in=today + timedelta(days=5),
                check_out=today + timedelta(days=7),
                source=Reservation.Source.WEBSITE,
                notes="Demo inquiry · Double",
                status=Reservation.Status.INQUIRY,
                adults=2,
            )
            self.stdout.write(f"Demo inquiry: {inquiry.code}")

        dirty_room = rooms["201"]
        if dirty_room.status != Room.Status.DIRTY:
            dirty_room.status = Room.Status.DIRTY
            dirty_room.save(update_fields=["status"])
        HousekeepingTask.objects.get_or_create(
            tenant=tenant,
            room=dirty_room,
            title="201 — tozalash",
            defaults={"status": HousekeepingTask.Status.PENDING},
        )

        Expense.objects.get_or_create(
            tenant=tenant,
            hotel=prop,
            title="Elektr energiya (qoralama)",
            defaults={
                "category": cat_kommunal,
                "vendor": vendor_util,
                "amount": Decimal("850000"),
                "expense_date": today,
                "status": Expense.Status.DRAFT,
                "created_by": user,
            },
        )
        approved_exp, _ = Expense.objects.get_or_create(
            tenant=tenant,
            hotel=prop,
            title="Oziq-ovqat xaridi",
            defaults={
                "category": cat_food,
                "vendor": vendor_food,
                "amount": Decimal("1200000"),
                "expense_date": today - timedelta(days=2),
                "status": Expense.Status.DRAFT,
                "created_by": user,
            },
        )
        if approved_exp.status == Expense.Status.DRAFT:
            approve_expense(approved_exp, user)

        paid_exp, _ = Expense.objects.get_or_create(
            tenant=tenant,
            hotel=prop,
            title="Internet xizmati",
            defaults={
                "category": cat_kommunal,
                "vendor": vendor_util,
                "amount": Decimal("350000"),
                "expense_date": today - timedelta(days=5),
                "status": Expense.Status.DRAFT,
                "created_by": user,
            },
        )
        if paid_exp.status != Expense.Status.PAID:
            if paid_exp.status == Expense.Status.DRAFT:
                approve_expense(paid_exp, user)
            if paid_exp.status == Expense.Status.APPROVED:
                mark_expense_paid(paid_exp, user)

        Expense.objects.get_or_create(
            tenant=tenant,
            hotel=prop,
            title="Konditsioner ta’miri",
            defaults={
                "category": cat_repair,
                "vendor": vendor_util,
                "amount": Decimal("450000"),
                "expense_date": today - timedelta(days=1),
                "status": Expense.Status.DRAFT,
                "created_by": user,
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Demo ready: demo / manager — demo12345 · "
                f"{RoomType.objects.filter(property=prop).count()} tur · "
                f"{Room.objects.filter(property=prop).count()} xona"
            )
        )
