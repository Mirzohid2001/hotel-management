from decimal import Decimal

from django.core.management.base import BaseCommand

from folio.services import correct_undercharged_emehmon, find_undercharged_emehmon
from tenants.models import Tenant


class Command(BaseCommand):
    help = (
        "Eski E-mehmon «1×tarif» yozuvlarini mehmon×kecha×tarifga to‘g‘rilaydi. "
        "Default: dry-run. Haqiqiy yozish: --apply"
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
            help="Charge/payment summalarini yangilash",
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
        rows = find_undercharged_emehmon(tenant=tenant)
        if not rows:
            self.stdout.write(self.style.SUCCESS("Kam olingan E-mehmon yo‘q."))
            return

        total_gap = sum((r["gap"] for r in rows), Decimal("0"))
        self.stdout.write(f"Topildi: {len(rows)} ta · jami farq {total_gap}")
        for row in rows[:40]:
            res = row["reservation"]
            self.stdout.write(
                f"  {res.code} | {res.guest} | "
                f"{row['guests']}×{row['nights']}={row['guests'] * row['nights']} | "
                f"{row['collected']} → {row['expected']} (+{row['gap']})"
            )
        if len(rows) > 40:
            self.stdout.write(f"  … yana {len(rows) - 40} ta")

        result = correct_undercharged_emehmon(tenant=tenant, dry_run=dry_run)
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY-RUN: {len(rows)} ta yozuv tuzatilardi. Ishga tushirish: --apply"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Tuzatildi: {len(result['corrected'])} ta E-mehmon yozuvi."
                )
            )
