from datetime import datetime

from django.core.management.base import BaseCommand

from core.cbu import CBUFetchError, sync_cbu_rates_all_tenants, sync_cbu_rates_for_tenant
from tenants.models import Tenant


class Command(BaseCommand):
    help = (
        "O‘zbekiston Markaziy bankidan (CBU) USD/EUR kurslarini yuklab, "
        "barcha aktiv tenantlarga saqlaydi. Cron: har kuni ertalab."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            default="",
            help="YYYY-MM-DD (bo‘sh = CBU joriy kursi)",
        )
        parser.add_argument(
            "--tenant",
            type=str,
            default="",
            help="Faqat shu tenant slug yoki id",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Shu sana uchun mavjud CBU yozuvini yangilash",
        )

    def handle(self, *args, **options):
        on_date = None
        raw_date = (options.get("date") or "").strip()
        if raw_date:
            on_date = datetime.strptime(raw_date, "%Y-%m-%d").date()

        force = bool(options.get("force"))
        tenant_key = (options.get("tenant") or "").strip()

        try:
            if tenant_key:
                qs = Tenant.objects.filter(is_active=True)
                if tenant_key.isdigit():
                    tenant = qs.filter(pk=int(tenant_key)).first()
                else:
                    tenant = qs.filter(slug=tenant_key).first()
                if tenant is None:
                    self.stderr.write(self.style.ERROR(f"Tenant topilmadi: {tenant_key}"))
                    return
                info = sync_cbu_rates_for_tenant(tenant, on_date=on_date, force=force)
                results = [{**info, "tenant": tenant.name, "ok": True}]
            else:
                results = sync_cbu_rates_all_tenants(on_date=on_date, force=force)
        except CBUFetchError as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            return

        ok_n = 0
        for row in results:
            if not row.get("ok", True):
                self.stderr.write(
                    self.style.WARNING(f"× {row.get('tenant')}: {row.get('error')}")
                )
                continue
            ok_n += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ {row['tenant']}: baza={row['base_currency']} "
                    f"sana={row['effective_on']} "
                    f"+{len(row['created'])} ~{len(row['updated'])} "
                    f"skip={len(row['skipped'])} · {row['rates']}"
                )
            )
        self.stdout.write(self.style.NOTICE(f"Tayyor: {ok_n}/{len(results)} tenant"))
