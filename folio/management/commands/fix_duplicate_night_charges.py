from django.core.management.base import BaseCommand

from folio.services import find_duplicate_night_charges, void_duplicate_night_charges
from tenants.models import Tenant


class Command(BaseCommand):
    help = (
        "Bir kecha uchun ikkilangan Night folio yozuvlarini topadi / bekor qiladi. "
        "Default: dry-run. Haqiqiy tozalash: --apply"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            type=str,
            default="",
            help="Tenant slug yoki id (bo‘sh = barcha)",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Dublikatlarni void qilish (eng eski qoladi)",
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

        dry_run = not options["apply"]
        groups = find_duplicate_night_charges(tenant=tenant)
        if not groups:
            self.stdout.write(self.style.SUCCESS("Dublikat Night yozuv yo‘q."))
            return

        self.stdout.write(f"Topildi: {len(groups)} ta dublikat guruh")
        for folio_id, day_key, items in groups[:50]:
            ids = ", ".join(str(c.pk) for c in items)
            code = ""
            res = getattr(items[0].folio, "reservation", None)
            if res is not None:
                code = res.code
            self.stdout.write(
                f"  folio={folio_id} {code} night={day_key} charges=[{ids}] "
                f"keep=#{items[0].pk} void={[c.pk for c in items[1:]]}"
            )
        if len(groups) > 50:
            self.stdout.write(f"  … yana {len(groups) - 50} guruh")

        result = void_duplicate_night_charges(
            tenant=tenant, dry_run=dry_run
        )
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY-RUN: {len(result['voided'])} ta yozuv void qilinardi. "
                    "Ishga tushirish: --apply"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Void qilindi: {len(result['voided'])} ta dublikat Night."
                )
            )
