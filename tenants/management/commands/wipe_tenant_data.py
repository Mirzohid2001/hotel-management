"""Wipe all operational data for one tenant; keep tenant + admin users + subscription."""

from __future__ import annotations

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import ForeignKey

from tenants.models import Tenant, TenantMembership


# Keep these even when wiping a tenant
KEEP_LABELS = {
    "tenants.Tenant",
    "tenants.TenantMembership",
    "tenants.MembershipProperty",  # cleared if properties gone; membership kept
    "subscriptions.Subscription",
    "subscriptions.Plan",
    "accounts.User",
    "auth.Group",
    "auth.Permission",
    "contenttypes.ContentType",
    "sessions.Session",
    "admin.LogEntry",
}


class Command(BaseCommand):
    help = (
        "O‘chiradi: bronlar, mehmonlar, kassa, moliya, xonalar… "
        "Saqlaydi: tenant, admin membership/user, obuna."
    )

    def add_arguments(self, parser):
        parser.add_argument("--slug", required=True, help="Tenant slug, masalan aida-hotel")
        parser.add_argument(
            "--confirm",
            required=True,
            help="Xavfsizlik: --confirm=<slug> (slug bilan bir xil bo‘lsin)",
        )
        parser.add_argument(
            "--also-property",
            action="store_true",
            help="Xonalar/filial/tarifni ham o‘chiradi (toza start)",
        )
        parser.add_argument(
            "--keep-property",
            action="store_true",
            help="Filial, xonalar, tarif, sozlamalarni saqlaydi",
        )

    def handle(self, *args, **options):
        slug = options["slug"].strip()
        if options["confirm"] != slug:
            raise CommandError("Xavfsizlik: --confirm qiymati --slug bilan bir xil bo‘lishi shart.")

        tenant = Tenant.objects.filter(slug=slug).first()
        if tenant is None:
            raise CommandError(f"Tenant topilmadi: {slug}")

        keep_property = options["keep_property"] and not options["also_property"]
        # Default: wipe property too (all data) unless --keep-property
        wipe_property = not keep_property

        memberships = list(
            TenantMembership.objects.filter(tenant=tenant).select_related("user")
        )
        if not memberships:
            self.stdout.write(self.style.WARNING("Diqqat: tenant membership yo‘q."))

        self.stdout.write(f"Tenant: {tenant.id} {tenant.slug} ({tenant.name})")
        for m in memberships:
            self.stdout.write(f"  KEEP user {m.user.username} role={m.role}")

        # Collect tenant-FK models (exclude keep list)
        to_wipe: list[tuple] = []
        for model in apps.get_models():
            label = model._meta.label
            if label in KEEP_LABELS:
                continue
            if model._meta.proxy or model._meta.auto_created:
                continue
            tenant_field = None
            for f in model._meta.fields:
                if isinstance(f, ForeignKey) and f.related_model is Tenant:
                    tenant_field = f.name
                    break
            if not tenant_field:
                continue
            if not wipe_property and label.startswith("properties."):
                self.stdout.write(f"  SKIP property model {label}")
                continue
            to_wipe.append((model, tenant_field, label))

        # Delete order: children-ish first by reversing dependency depth heuristic —
        # delete high-count operational tables first, Property last.
        priority = {
            "folio.GuestPayment": 10,
            "folio.FolioCharge": 10,
            "folio.CompanyPayment": 10,
            "folio.CompanyInvoiceLine": 10,
            "folio.CompanyInvoice": 20,
            "folio.CashShiftMovement": 10,
            "folio.CashShift": 30,
            "folio.Folio": 40,
            "bookings.ReservationChangeLog": 10,
            "bookings.Stay": 20,
            "bookings.Reservation": 40,
            "bookings.ReservationGroup": 50,
            "bookings.ReferrerCommissionPayment": 20,
            "bookings.BookingReferrer": 60,
            "housekeeping.HousekeepingTask": 20,
            "housekeeping.RoomStatusLog": 20,
            "hr.SalaryPayment": 10,
            "hr.SalaryAdvance": 10,
            "hr.PayrollItem": 20,
            "hr.PayrollPeriod": 30,
            "hr.Employee": 40,
            "inventory.MinibarSale": 10,
            "inventory.StockMovement": 10,
            "inventory.StockItem": 30,
            "finance.ProfitWithdrawal": 10,
            "finance.ProfitPeriod": 20,
            "finance.ProfitPartner": 30,
            "finance.Expense": 20,
            "finance.ExpenseCategory": 40,
            "finance.Vendor": 40,
            "maintenance.MaintenanceTicket": 20,
            "services.ServiceOrder": 20,
            "services.ServiceItem": 30,
            "guests.GuestDocument": 10,
            "guests.GuestNote": 10,
            "guests.Guest": 40,
            "guests.Company": 40,
            "reports.NightAuditRun": 20,
            "core.ActivityLog": 10,
            "tenants.ExchangeRate": 20,
            "widget.WidgetConfig": 50,
            "properties.SeasonRate": 20,
            "properties.RatePlan": 30,
            "properties.Room": 40,
            "properties.RoomType": 50,
            "properties.Floor": 50,
            "properties.PropertySettings": 50,
            "properties.Property": 90,
        }
        to_wipe.sort(key=lambda x: (priority.get(x[2], 70), x[2]))

        with transaction.atomic():
            # Clear property assignments pointing at this tenant's properties
            from tenants.models import MembershipProperty

            prop_ids = list(
                apps.get_model("properties.Property")
                .objects.filter(tenant=tenant)
                .values_list("id", flat=True)
            )
            if prop_ids:
                deleted_mp, _ = MembershipProperty.objects.filter(
                    property_id__in=prop_ids
                ).delete()
                self.stdout.write(f"  MembershipProperty deleted={deleted_mp}")

            totals = {}
            for model, field, label in to_wipe:
                qs = model.objects.filter(**{field: tenant})
                n = qs.count()
                if n == 0:
                    continue
                deleted, detail = qs.delete()
                totals[label] = deleted
                self.stdout.write(f"  {label}: deleted={deleted}")

            # Ensure memberships still exist
            left = TenantMembership.objects.filter(tenant=tenant).count()
            if left == 0:
                raise CommandError("Xato: membershiplar o‘chib ketdi — rollback.")

            # Subscription must remain
            from subscriptions.models import Subscription

            if not Subscription.objects.filter(tenant=tenant).exists():
                raise CommandError("Xato: subscription yo‘qoldi — rollback.")

        self.stdout.write(self.style.SUCCESS(f"OK: {slug} tozalandi. Tenant+admin+obuna saqlandi."))
        for m in TenantMembership.objects.filter(tenant=tenant).select_related("user"):
            self.stdout.write(f"  user={m.user.username} role={m.role}")
