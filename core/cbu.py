"""O‘zbekiston Markaziy banki (CBU) valyuta kurslari."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from core.currency import CURRENCY_CODES, normalize_currency

logger = logging.getLogger(__name__)

CBU_JSON_URL = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"
CBU_JSON_BY_DATE = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/all/{date}/"
CBU_TRACKED = ("USD", "EUR")
CBU_USER_AGENT = "HotelPMS-CBU/1.0 (+https://cbu.uz)"
CBU_NOTE = "Markaziy bank (CBU) · avtomatik"


class CBUFetchError(ValidationError):
    """Markaziy bankdan kurs olishda xato."""


def expected_cbu_business_day(on_day: date | None = None) -> date:
    """
    Bugungi kunda kutiladigan oxirgi CBU ish kuni.
    Shanba/yakshanba → juma (yoki oldingi ish kuni).
    """
    d = on_day or timezone.localdate()
    while d.weekday() >= 5:  # 5=Sat, 6=Sun
        d -= timedelta(days=1)
    return d


def _parse_cbu_date(raw: str) -> date:
    raw = (raw or "").strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return timezone.localdate()


def _http_get_json(url: str, *, timeout: int = 20) -> list | dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": CBU_USER_AGENT,
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise CBUFetchError(
            _("Markaziy bank javob bermadi (HTTP %(code)s).") % {"code": exc.code}
        ) from exc
    except urllib.error.URLError as exc:
        raise CBUFetchError(
            _("Markaziy bankka ulanishning iloji bo‘lmadi: %(err)s") % {"err": exc.reason}
        ) from exc
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise CBUFetchError(_("Markaziy bank javobi JSON emas.")) from exc


def fetch_cbu_rates_to_uzs(*, on_date: date | None = None) -> dict[str, dict]:
    """
    CBU dan USD/EUR kurslarini olish (1 birlik = Rate so‘m).

    Qaytadi: {"USD": {"rate": Decimal, "nominal": 1, "effective_on": date}, ...}
    """
    if on_date is None:
        url = CBU_JSON_URL
    else:
        url = CBU_JSON_BY_DATE.format(date=on_date.isoformat())

    payload = _http_get_json(url)
    if not isinstance(payload, list):
        raise CBUFetchError(_("Markaziy bank formati kutilgandek emas."))

    out: dict[str, dict] = {}
    for row in payload:
        code = (row.get("Ccy") or "").upper()
        if code not in CBU_TRACKED:
            continue
        try:
            rate = Decimal(str(row.get("Rate", "0")).replace(",", "."))
            nominal = Decimal(str(row.get("Nominal") or "1").replace(",", "."))
        except (InvalidOperation, TypeError) as exc:
            raise CBUFetchError(_("Kurs soni noto‘g‘ri: %(c)s") % {"c": code}) from exc
        if rate <= 0 or nominal <= 0:
            continue
        # Nominal > 1 bo‘lsa (masalan 100 JPY) — 1 birlikka keltiramiz
        per_unit = (rate / nominal).quantize(Decimal("0.000001"))
        out[code] = {
            "rate": per_unit,
            "nominal": nominal,
            "effective_on": _parse_cbu_date(str(row.get("Date") or "")),
            "raw_rate": rate,
        }
    if not out:
        raise CBUFetchError(_("USD/EUR kurslari topilmadi."))
    return out


def rates_for_base(base_currency: str, cbu_to_uzs: dict[str, dict]) -> dict[str, Decimal]:
    """
    CBU (UZS) kurslaridan tenant bazaviy valyutasiga mos kurslar.

    Natija: {currency: rate} — 1 currency = rate × base.
    """
    base = normalize_currency(base_currency or "UZS")
    uzs = {code: data["rate"] for code, data in cbu_to_uzs.items()}
    result: dict[str, Decimal] = {}

    if base == "UZS":
        for code, rate in uzs.items():
            result[code] = rate
        return result

    # base USD yoki EUR — UZS va boshqa valyutani shu bazaga o‘tkazish
    if base not in uzs:
        raise CBUFetchError(
            _("Bazaviy %(b)s uchun Markaziy bank kursi yo‘q.") % {"b": base}
        )
    base_in_uzs = uzs[base]
    # 1 UZS = 1/base_in_uzs base
    result["UZS"] = (Decimal("1") / base_in_uzs).quantize(Decimal("0.000001"))
    for code, rate_uzs in uzs.items():
        if code == base:
            continue
        # 1 EUR = (EUR_uzs / USD_uzs) USD
        result[code] = (rate_uzs / base_in_uzs).quantize(Decimal("0.000001"))
    return result


def _apply_cbu_to_tenant(
    tenant,
    cbu: dict[str, dict],
    *,
    on_date: date | None = None,
    force: bool = False,
) -> dict:
    """HTTP yo‘q — faqat DB yozuv (atomic ichida chaqiriladi)."""
    from tenants.models import ExchangeRate

    # effective_on — CBU dagi sana (odatda bugun yoki oldingi ish kuni)
    effective = next(iter(cbu.values()))["effective_on"]
    if on_date is not None:
        effective = on_date

    base = normalize_currency(getattr(tenant, "currency", None) or "UZS")
    mapped = rates_for_base(base, cbu)
    created, updated, skipped = [], [], []
    note = _(CBU_NOTE)

    for code, rate in mapped.items():
        if code not in CURRENCY_CODES or code == base:
            continue
        existing = ExchangeRate.objects.filter(
            tenant=tenant,
            currency=code,
            base_currency=base,
            effective_on=effective,
        ).first()
        if existing and not force:
            # Qo‘lda yoki avvalgi CBU — shu sana uchun qayta yozmaymiz
            skipped.append(code)
            continue
        if existing:
            existing.rate = rate
            existing.note = note
            existing.save(update_fields=["rate", "note", "updated_at"])
            updated.append(code)
        else:
            ExchangeRate.objects.create(
                tenant=tenant,
                currency=code,
                base_currency=base,
                rate=rate,
                effective_on=effective,
                note=note,
            )
            created.append(code)

    # Tarmoq chaqiruvi bo‘ldi, lekin yozuv o‘zgarmadi — "bugun tekshirildi" deb belgilash
    if not created and not updated and skipped:
        ExchangeRate.objects.filter(
            tenant=tenant,
            base_currency=base,
            effective_on=effective,
            currency__in=skipped,
        ).update(updated_at=timezone.now())

    return {
        "effective_on": effective,
        "base_currency": base,
        "rates": mapped,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "cbu_raw": {k: str(v["rate"]) for k, v in cbu.items()},
    }


def sync_cbu_rates_for_tenant(
    tenant,
    *,
    on_date: date | None = None,
    force: bool = False,
    cbu: dict[str, dict] | None = None,
) -> dict:
    """
    Tenant uchun CBU kurslarini saqlash.

    force=False: shu sana uchun allaqachon yozuv bo‘lsa, qayta yozmaydi.
    HTTP chaqiruvi transaction tashqarisida — DB ulanishini ushlab turmaydi.
    """
    if cbu is None:
        cbu = fetch_cbu_rates_to_uzs(on_date=on_date)
    with transaction.atomic():
        return _apply_cbu_to_tenant(tenant, cbu, on_date=on_date, force=force)


def sync_cbu_rates_all_tenants(*, on_date: date | None = None, force: bool = False) -> list[dict]:
    """Bitta CBU so‘rovi → barcha aktiv tenantlarga yozish."""
    from tenants.models import Tenant

    cbu = fetch_cbu_rates_to_uzs(on_date=on_date)
    results = []
    for tenant in Tenant.objects.filter(is_active=True):
        try:
            info = sync_cbu_rates_for_tenant(
                tenant, on_date=on_date, force=force, cbu=cbu
            )
            info["tenant_id"] = tenant.pk
            info["tenant"] = tenant.name
            info["ok"] = True
            results.append(info)
        except CBUFetchError as exc:
            logger.warning("CBU sync failed for tenant %s: %s", tenant.pk, exc)
            results.append(
                {
                    "tenant_id": tenant.pk,
                    "tenant": tenant.name,
                    "ok": False,
                    "error": "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
                }
            )
    return results


def _start_of_local_day():
    return timezone.make_aware(
        datetime.combine(timezone.localdate(), datetime.min.time())
    )


def has_fresh_cbu_rates(tenant) -> bool:
    """Joriy ish kuni uchun (yoki bugun tekshirilgan) CBU kursi bormi?"""
    from tenants.models import ExchangeRate

    today = timezone.localdate()
    base = normalize_currency(getattr(tenant, "currency", None) or "UZS")
    needed = [c for c in ("USD", "EUR", "UZS") if c != base]
    expected = expected_cbu_business_day(today)

    qs = ExchangeRate.objects.filter(
        tenant=tenant,
        base_currency=base,
        currency__in=needed,
        note__icontains="CBU",
    )
    # Oxirgi CBU sanasi kutilgan ish kuniga yetadi
    if qs.filter(effective_on__gte=expected).exists():
        return True
    # Bugun allaqachon CBU ga murojaat qilingan (kurs o‘zgarmagan bo‘lsa ham)
    if qs.filter(updated_at__gte=_start_of_local_day()).exists():
        return True
    return False


def ensure_today_cbu_rates(tenant, *, force: bool = False) -> dict | None:
    """
    Kerakli CBU kursi yo‘q / eskirgan bo‘lsa — bir marta yuklash.
    Dam olish kunida juma kursi yetarli; dushanba yangi kursni oladi.
    Tarmoq xatosida None (fallback default kurslar ishlayveradi).
    """
    from tenants.models import ExchangeRate

    today = timezone.localdate()
    base = normalize_currency(getattr(tenant, "currency", None) or "UZS")
    needed = [c for c in ("USD", "EUR", "UZS") if c != base]

    if not force and has_fresh_cbu_rates(tenant):
        return None

    # Qo‘lda kiritilgan bugungi kurs — CBU ni majburlamaymiz
    has_today_manual = ExchangeRate.objects.filter(
        tenant=tenant,
        base_currency=base,
        effective_on=today,
        currency__in=needed,
    ).exclude(note__icontains="CBU").exists()
    if has_today_manual and not force:
        return None

    try:
        return sync_cbu_rates_for_tenant(tenant, force=force)
    except CBUFetchError as exc:
        logger.info("CBU ensure skipped: %s", exc)
        return None
