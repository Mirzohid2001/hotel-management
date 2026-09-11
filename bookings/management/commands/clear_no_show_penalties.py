from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from bookings.services import clear_existing_no_show_penalties
from tenants.models import Tenant


class Command(BaseCommand):
    help = (
        "Kelmagan (no-show) bronlardagi jarima/yashash yozuvlarini tozalaydi. "
        "Default: dry-run. Haqiqiy tozalash: --apply"
    )

    def add_arguments(self, parser):
        parser.add_argument("--tenant", type=str, default="", help="Tenant slug yoki id")
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Jarimalarni void qilish va to‘lovni qaytarish",
        )

    def handle(self, *args, **options):
        tenant = None
        raw = (options.get("tenant") or "").strip()
        if raw:
            if raw.isdigit():
                tenant = Tenant.objects.filter(pk=int(raw)).first()
            else:
                tenant = Tenant.objects.filter(slug=raw).first()
            if tenant is None:
                self.stderr.write(self.style.ERROR(f"Tenant topilmadi: {raw}"))
                return

        User = get_user_model()
        user = User.objects.filter(is_superuser=True).order_by("id").first()
        if user is None and tenant is not None:
            from tenants.models import Membership

            m = Membership.objects.filter(tenant=tenant).select_related("user").first()
            user = m.user if m else None

        result = clear_existing_no_show_penalties(
            tenant=tenant, user=user, dry_run=not options["apply"]
        )
        codes = ", ".join(result["reservations"][:30]) or "—"
        self.stdout.write(
            f"Bronlar: {len(result['reservations'])} [{codes}] · "
            f"void kandidat: {result['void_candidates']}"
        )
        if result["dry_run"]:
            self.stdout.write(
                self.style.WARNING("DRY-RUN. Ishga tushirish: --apply")
            )
        else:
            self.stdout.write(self.style.SUCCESS("Tozalandi (jarimasiz siyosat)."))
