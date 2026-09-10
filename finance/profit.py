"""Partner profit share: net in period, entitlements, withdrawals, reset."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import ProfitPartner, ProfitPeriod, ProfitWithdrawal

ZERO = Decimal("0.00")
HUNDRED = Decimal("100")


def _q(amount) -> Decimal:
    return Decimal(amount or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_open_period(tenant) -> ProfitPeriod | None:
    return ProfitPeriod.objects.filter(tenant=tenant, ended_on__isnull=True).first()


@transaction.atomic
def ensure_open_period(tenant, *, started_on: date | None = None) -> ProfitPeriod:
    open_period = get_open_period(tenant)
    if open_period:
        return open_period
    start = started_on or timezone.localdate()
    return ProfitPeriod.objects.create(tenant=tenant, started_on=start)


def active_partners(tenant):
    return ProfitPartner.objects.filter(tenant=tenant, is_active=True)


def active_share_total(tenant) -> Decimal:
    total = active_partners(tenant).aggregate(s=Sum("share_percent"))["s"]
    return _q(total)


def period_bounds(period: ProfitPeriod, *, today: date | None = None) -> tuple[date, date]:
    today = today or timezone.localdate()
    end = period.ended_on or today
    if end < period.started_on:
        end = period.started_on
    return period.started_on, end


def build_partner_ledger(tenant, *, period: ProfitPeriod | None = None, hotel=None) -> dict:
    """
    Sof (operatsion) = tushum − joriy rasxod − oylik − komissiya − ombor …
    Reinvestitsiya Sofga kirmaydi; taqsimlash: Sof − reinvestitsiya.
    """
    from reports.accounting import cash_pnl_for_range, reinvestment_in_range

    period = period or ensure_open_period(tenant)
    start, end = period_bounds(period)
    pnl = cash_pnl_for_range(tenant, start, end, hotel=hotel)
    operating_net = _q(pnl["net"])
    reinvestment = _q(reinvestment_in_range(tenant, start, end, hotel=hotel))
    net = _q(operating_net - reinvestment)

    withdrawals = (
        ProfitWithdrawal.objects.filter(tenant=tenant, period=period)
        .select_related("partner")
        .order_by("-paid_on", "-id")
    )
    withdrawn_by_partner: dict[int, Decimal] = {}
    for w in withdrawals:
        withdrawn_by_partner[w.partner_id] = withdrawn_by_partner.get(w.partner_id, ZERO) + _q(
            getattr(w, "amount_base", None) or w.amount
        )

    partners = list(active_partners(tenant))
    share_sum = sum((_q(p.share_percent) for p in partners), ZERO)
    rows = []
    entitled_total = ZERO
    withdrawn_total = ZERO
    remaining_total = ZERO
    for p in partners:
        pct = _q(p.share_percent)
        entitled = _q(net * pct / HUNDRED) if net > 0 else ZERO
        # Zarar bo‘lsa ulush ham manfiy ko‘rinadi (moslashuvchan)
        if net < 0:
            entitled = _q(net * pct / HUNDRED)
        withdrawn = withdrawn_by_partner.get(p.pk, ZERO)
        remaining = _q(entitled - withdrawn)
        entitled_total += entitled
        withdrawn_total += withdrawn
        remaining_total += remaining
        rows.append(
            {
                "partner": p,
                "share_percent": pct,
                "entitled": entitled,
                "withdrawn": withdrawn,
                "remaining": remaining,
            }
        )

    # Inactive partners that still withdrew in this period
    for pid, amt in withdrawn_by_partner.items():
        if any(r["partner"].pk == pid for r in rows):
            continue
        partner = ProfitPartner.objects.filter(pk=pid, tenant=tenant).first()
        if partner is None:
            continue
        rows.append(
            {
                "partner": partner,
                "share_percent": _q(partner.share_percent),
                "entitled": ZERO,
                "withdrawn": amt,
                "remaining": _q(ZERO - amt),
                "inactive": True,
            }
        )
        withdrawn_total += amt
        remaining_total += _q(ZERO - amt)

    entitled_total = _q(entitled_total)
    withdrawn_total = _q(withdrawn_total)
    remaining_total = _q(remaining_total)
    undistributed = _q(net - entitled_total) if net >= 0 else ZERO
    share_gap = _q(HUNDRED - share_sum) if share_sum < HUNDRED else ZERO

    # Next-step hints for the UI
    next_steps = []
    if not partners:
        next_steps.append(
            {
                "key": "add_partner",
                "tone": "warn",
                "text": _("Avval sheriklarni qo‘shing (ulushlar yig‘indisi 100% bo‘lsin)."),
            }
        )
    elif share_gap > 0:
        next_steps.append(
            {
                "key": "share_gap",
                "tone": "warn",
                "text": _(
                    "Hali %(gap)s%% ulush biriktirilmagan — qolgan sheriklarni qo‘shing yoki foizlarni 100%% ga to‘ldiring."
                )
                % {"gap": share_gap},
            }
        )
    if remaining_total > 0:
        next_steps.append(
            {
                "key": "withdraw",
                "tone": "info",
                "text": _(
                    "Sheriklar hali %(r)s olishi mumkin. Qoldiqni «Olish» orqali yozing."
                )
                % {"r": remaining_total},
            }
        )
    if withdrawn_total > 0 and remaining_total <= 0 and partners:
        next_steps.append(
            {
                "key": "reset",
                "tone": "ok",
                "text": _(
                    "Bu davrdagi ulushlar yopildi. «0 qilib qayta» — yangi sof hisobni boshlang."
                ),
            }
        )
    elif withdrawn_total > 0 and remaining_total > 0:
        next_steps.append(
            {
                "key": "partial",
                "tone": "info",
                "text": _(
                    "Qisman olindi. Qolganini oling yoki tayyor bo‘lsangiz davrni 0 qilib yangilang."
                ),
            }
        )

    return {
        "period": period,
        "start": start,
        "end": end,
        "pnl": pnl,
        "operating_net": operating_net,
        "reinvestment": reinvestment,
        "net": net,
        "distributable": net,
        "share_sum": share_sum,
        "share_ok": share_sum == HUNDRED,
        "share_gap": share_gap,
        "undistributed": undistributed,
        "rows": rows,
        "entitled_total": entitled_total,
        "withdrawn_total": withdrawn_total,
        "remaining_total": remaining_total,
        "withdrawals": list(withdrawals[:40]),
        "next_steps": next_steps,
        "ready_to_reset": withdrawn_total > 0 and remaining_total <= 0 and bool(partners),
    }


@transaction.atomic
def record_withdrawal(
    tenant,
    user,
    *,
    partner: ProfitPartner,
    amount: Decimal,
    paid_on: date | None = None,
    payment_method: str = ProfitWithdrawal.PaymentMethod.CASH,
    note: str = "",
    allow_overdraw: bool = False,
    currency: str | None = None,
) -> ProfitWithdrawal:
    if partner.tenant_id != tenant.id:
        raise ValidationError(_("Sherik topilmadi."))
    amount = _q(amount)
    if amount <= 0:
        raise ValidationError(_("Summa 0 dan katta bo‘lishi kerak."))

    from core.currency import to_base_amount

    pay_currency = currency or tenant.currency or "UZS"
    period = ensure_open_period(tenant)
    ledger = build_partner_ledger(tenant, period=period)
    row = next((r for r in ledger["rows"] if r["partner"].pk == partner.pk), None)
    remaining = row["remaining"] if row else ZERO
    _cur, _rate, amount_base = to_base_amount(tenant, amount, pay_currency)
    if not allow_overdraw and amount_base > remaining:
        raise ValidationError(
            _("Ulush qoldig‘idan ko‘p: qolgan %(r)s %(cur)s, so‘ralgan %(a)s %(pay)s.")
            % {
                "r": remaining,
                "cur": tenant.currency or "UZS",
                "a": amount,
                "pay": pay_currency,
            }
        )

    return ProfitWithdrawal.objects.create(
        tenant=tenant,
        period=period,
        partner=partner,
        amount=amount,
        currency=pay_currency,
        paid_on=paid_on or timezone.localdate(),
        payment_method=payment_method,
        note=note,
        created_by=user,
    )


@transaction.atomic
def reset_profit_period(
    tenant,
    user,
    *,
    ended_on: date | None = None,
    note: str = "",
    new_start: date | None = None,
    restart_today: bool = False,
) -> tuple[ProfitPeriod, ProfitPeriod]:
    """
    Joriy davrni yopadi (0 dan qayta hisob) va yangi ochiq davr boshlaydi.
    restart_today=True → yangi davr bugundan (shu kun tushumi qayta ulashiladi).
    """
    period = ensure_open_period(tenant)
    end = ended_on or timezone.localdate()
    if end < period.started_on:
        raise ValidationError(_("Tugash sanasi boshlanishdan oldin bo‘lishi mumkin emas."))

    ledger = build_partner_ledger(tenant, period=period)
    period.ended_on = end
    period.closed_at = timezone.now()
    period.closed_by = user
    period.note = note or period.note
    period.net_snapshot = ledger["net"]
    period.save(
        update_fields=[
            "ended_on",
            "closed_at",
            "closed_by",
            "note",
            "net_snapshot",
            "updated_at",
        ]
    )

    if new_start is not None:
        start = new_start
    elif restart_today:
        start = end
    else:
        start = end + timedelta(days=1)
    if ProfitPeriod.objects.filter(tenant=tenant, ended_on__isnull=True).exists():
        raise ValidationError(_("Allaqachon ochiq davr bor."))
    fresh = ProfitPeriod.objects.create(tenant=tenant, started_on=start)
    return period, fresh
