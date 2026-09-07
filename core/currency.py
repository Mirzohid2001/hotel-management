"""Multi-currency (UZS / USD / EUR) — bazaviy valyuta + kurs."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from tenants.models import Tenant

CURRENCY_CHOICES = [
    ("UZS", _("So‘m (UZS)")),
    ("USD", _("Dollar (USD)")),
    ("EUR", _("Euro (EUR)")),
]

CURRENCY_CODES = frozenset(c[0] for c in CURRENCY_CHOICES)

CURRENCY_SYMBOLS = {
    "UZS": "so‘m",
    "USD": "$",
    "EUR": "€",
}

# Agar kurs jadvali bo‘sh bo‘lsa — taxminiy defaultlar (UZS bazaga)
DEFAULT_RATES_TO_UZS = {
    "UZS": Decimal("1"),
    "USD": Decimal("12700"),
    "EUR": Decimal("13800"),
}


def normalize_currency(code: str | None, *, default: str = "UZS") -> str:
    code = (code or default).upper().strip()
    if code not in CURRENCY_CODES:
        raise ValidationError(_("Valyuta faqat UZS, USD yoki EUR bo‘lishi mumkin."))
    return code


def currency_label(code: str) -> str:
    return dict(CURRENCY_CHOICES).get(code, code)


def currency_symbol(code: str) -> str:
    return CURRENCY_SYMBOLS.get(code, code)


class MoneyFieldsMixin(models.Model):
    """Tranzaksiya valyutasi + bazaviy ekvivalent."""

    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default="UZS",
        db_index=True,
    )
    fx_rate = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal("1"),
        help_text="1 birlik valyuta = fx_rate × bazaviy valyuta",
    )
    amount_base = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Bazaviy valyutadagi summa (hisobotlar uchun)",
    )

    class Meta:
        abstract = True


def get_rate_to_base(
    tenant: Tenant,
    currency: str,
    *,
    on_date: date | None = None,
    base_currency: str | None = None,
) -> Decimal:
    """Valyutadan tenant bazaviy valyutasiga kurs."""
    from tenants.models import ExchangeRate

    base = normalize_currency(base_currency or getattr(tenant, "currency", None) or "UZS")
    currency = normalize_currency(currency, default=base)
    if currency == base:
        return Decimal("1")

    day = on_date or timezone.localdate()
    row = (
        ExchangeRate.objects.filter(
            tenant=tenant,
            currency=currency,
            base_currency=base,
            effective_on__lte=day,
        )
        .order_by("-effective_on")
        .first()
    )
    if row:
        return row.rate

    # Fallback: agar baza UZS bo‘lmasa, USD↔EUR orqali yoki default
    if base == "UZS":
        return DEFAULT_RATES_TO_UZS.get(currency, Decimal("1"))
    if currency == "UZS" and base in DEFAULT_RATES_TO_UZS:
        # UZS → USD/EUR
        uzs_per_unit = DEFAULT_RATES_TO_UZS[base]
        if uzs_per_unit > 0:
            return (Decimal("1") / uzs_per_unit).quantize(Decimal("0.000001"))
    # USD ↔ EUR via UZS defaults
    uzs_from = DEFAULT_RATES_TO_UZS.get(currency)
    uzs_to = DEFAULT_RATES_TO_UZS.get(base)
    if uzs_from and uzs_to and uzs_to > 0:
        return (uzs_from / uzs_to).quantize(Decimal("0.000001"))
    return Decimal("1")


def to_base_amount(
    tenant: Tenant,
    amount: Decimal,
    currency: str | None = None,
    *,
    fx_rate: Decimal | None = None,
    on_date: date | None = None,
) -> tuple[str, Decimal, Decimal]:
    """
    Qaytaradi: (currency, fx_rate, amount_base).
    """
    base = normalize_currency(getattr(tenant, "currency", None) or "UZS")
    currency = normalize_currency(currency or base, default=base)
    amount = Decimal(amount or 0)
    if fx_rate is None:
        fx_rate = get_rate_to_base(tenant, currency, on_date=on_date, base_currency=base)
    else:
        fx_rate = Decimal(fx_rate)
    if currency == base:
        fx_rate = Decimal("1")
        amount_base = amount.quantize(Decimal("0.01"))
    else:
        amount_base = (amount * fx_rate).quantize(Decimal("0.01"))
    return currency, fx_rate, amount_base


def apply_money(
    instance,
    *,
    amount_attr: str = "amount",
    tenant=None,
    on_date: date | None = None,
    fx_rate: Decimal | None = None,
) -> None:
    """Model instance uchun currency/fx_rate/amount_base ni to‘ldirish."""
    tenant = tenant or getattr(instance, "tenant", None)
    if tenant is None:
        return
    amount = getattr(instance, amount_attr, None) or Decimal("0")
    base = normalize_currency(getattr(tenant, "currency", None) or "UZS")
    currency = normalize_currency(
        getattr(instance, "currency", None) or base, default=base
    )
    # Kurs: aniq berilgan yoki _lock_fx + instance.fx_rate; aks holda jadvaldan
    use_fx = fx_rate
    if use_fx is None and getattr(instance, "_lock_fx", False):
        locked = getattr(instance, "fx_rate", None)
        if locked is not None and locked > 0:
            use_fx = locked
    currency, resolved_rate, amount_base = to_base_amount(
        tenant, amount, currency, fx_rate=use_fx, on_date=on_date
    )
    instance.currency = currency
    instance.fx_rate = resolved_rate
    instance.amount_base = amount_base


def money_sum(qs, *, field: str = "amount_base") -> Decimal:
    from django.db.models import Sum

    return qs.aggregate(s=Sum(field))["s"] or Decimal("0")
