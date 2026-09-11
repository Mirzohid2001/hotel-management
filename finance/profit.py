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


def _major_share_partner(partners: list[ProfitPartner]) -> ProfitPartner | None:
    """Ulushi eng katta sherik (teng bo‘lsa — eng kichik pk)."""
    if not partners:
        return None
    return max(partners, key=lambda p: (_q(p.share_percent), -p.pk))


def _receipt_line(sign: str, label: str, amount: Decimal, *, tone: str = "", note: str = "") -> dict:
    return {
        "sign": sign,
        "label": label,
        "amount": _q(amount),
        "tone": tone,
        "note": note,
    }


def build_profit_receipt(ledger: dict) -> dict:
    """
    Chek/bayonnoma: har bir operatsiya qayerga qancha ketganini ochiq ko‘rsatadi.
    """
    pnl = ledger.get("pnl") or {}
    sections = []

    sof_lines = [
        _receipt_line("+", _("Mehmon to‘lovlari"), pnl.get("guest_payments") or ZERO),
        _receipt_line("+", _("Kompaniya to‘lovlari"), pnl.get("company_payments") or ZERO),
        _receipt_line("=", _("Tushum jami"), pnl.get("revenue_total") or ZERO, tone="subtotal"),
        _receipt_line("−", _("Rasxod (joriy)"), pnl.get("expenses_total") or ZERO),
        _receipt_line("−", _("Mehnat (yalpi)"), pnl.get("labor_total") or ZERO),
        _receipt_line("−", _("Yo‘naltiruvchi komissiya"), pnl.get("commission") or ZERO),
        _receipt_line("−", _("Ombor tannarx"), pnl.get("inventory_cost") or ZERO),
        _receipt_line("−", _("E-mehmon farq"), pnl.get("emehmon_shortfall") or ZERO),
        _receipt_line(
            "=",
            _("Sof foyda"),
            ledger.get("operating_net") or ZERO,
            tone="total",
            note=_("Ulushlar shu summadan hisoblanadi"),
        ),
    ]
    sections.append(
        {
            "key": "sof",
            "title": _("1. Sof foyda hisobi"),
            "hint": _("Tushum minus operatsion xarajatlar. Reinvestitsiya bu yerga kirmaydi."),
            "lines": sof_lines,
        }
    )

    share_lines = []
    for row in ledger.get("rows") or []:
        if row.get("inactive"):
            continue
        partner = row["partner"]
        pct = row["share_percent"]
        share_lines.append(
            _receipt_line(
                "+",
                _("%(name)s — %(pct)s%% × sof foyda")
                % {"name": partner.name, "pct": pct},
                row.get("gross_entitled") or ZERO,
                note=_("Sof foydadan ulush"),
            )
        )
        if row.get("reinvestment_cut"):
            share_lines.append(
                _receipt_line(
                    "−",
                    _("Reinvestitsiya (%(name)s ulushidan)")
                    % {"name": partner.name},
                    row["reinvestment_cut"],
                    tone="warn",
                    note=_("Ulushi eng katta sherikdan ayiriladi"),
                )
            )
            share_lines.append(
                _receipt_line(
                    "=",
                    _("%(name)s — sof ulush") % {"name": partner.name},
                    row.get("entitled") or ZERO,
                    tone="subtotal",
                )
            )
        if row.get("withdrawn"):
            share_lines.append(
                _receipt_line(
                    "−",
                    _("Olingan (%(name)s)") % {"name": partner.name},
                    row["withdrawn"],
                )
            )
        share_lines.append(
            _receipt_line(
                "=",
                _("%(name)s — qoldiq") % {"name": partner.name},
                row.get("remaining") or ZERO,
                tone="partner",
            )
        )

    if ledger.get("reinvestment") and not ledger.get("reinvestment_partner"):
        share_lines.append(
            _receipt_line(
                "−",
                _("Reinvestitsiya (sherik biriktirilmagan)"),
                ledger["reinvestment"],
                tone="warn",
            )
        )

    share_lines.append(
        _receipt_line(
            "=",
            _("Taqsimlanadigan jami (ulushlar)"),
            ledger.get("distributable") or ZERO,
            tone="total",
        )
    )
    if ledger.get("undistributed"):
        share_lines.append(
            _receipt_line(
                "·",
                _("Taqsimlanmagan (%(gap)s%%)")
                % {"gap": ledger.get("share_gap") or ZERO},
                ledger["undistributed"],
                note=_("Ulushlar 100%% bo‘lmagani uchun"),
            )
        )
    share_lines.append(
        _receipt_line(
            "=",
            _("Jami qoldiq (olish mumkin)"),
            ledger.get("remaining_total") or ZERO,
            tone="total",
        )
    )

    reinvest_hint = _("Avval sof foydadan foiz, keyin reinvestitsiya ulushi katta sherikdan.")
    if ledger.get("reinvestment_partner"):
        reinvest_hint = _(
            "Reinvestitsiya %(name)s (%(pct)s%%) ulushidan ayiriladi."
        ) % {
            "name": ledger["reinvestment_partner"].name,
            "pct": _q(ledger["reinvestment_partner"].share_percent),
        }

    sections.append(
        {
            "key": "share",
            "title": _("2. Sheriklar bo‘yicha taqsimlash"),
            "hint": reinvest_hint,
            "lines": share_lines,
        }
    )

    return {
        "title": _("Foyda ulushi — chek hisobot"),
        "start": ledger.get("start"),
        "end": ledger.get("end"),
        "sections": sections,
        "currency": None,
    }


def serialize_ledger_snapshot(ledger: dict) -> dict:
    """Yopilgan davr uchun JSON-serializable tarix snaypi."""
    receipt = ledger.get("receipt") or {}
    pnl = ledger.get("pnl") or {}

    def _sec(section: dict) -> dict:
        return {
            "key": section.get("key"),
            "title": str(section.get("title") or ""),
            "hint": str(section.get("hint") or ""),
            "lines": [
                {
                    "sign": line.get("sign"),
                    "label": str(line.get("label") or ""),
                    "amount": str(line.get("amount") or "0"),
                    "tone": line.get("tone") or "",
                    "note": str(line.get("note") or ""),
                }
                for line in (section.get("lines") or [])
            ],
        }

    return {
        "net": str(ledger.get("net") or ZERO),
        "operating_net": str(ledger.get("operating_net") or ZERO),
        "reinvestment": str(ledger.get("reinvestment") or ZERO),
        "distributable": str(ledger.get("distributable") or ZERO),
        "revenue_total": str(pnl.get("revenue_total") or ZERO),
        "operating_costs": str(pnl.get("operating_costs") or ZERO),
        "reinvestment_partner": (
            ledger["reinvestment_partner"].name
            if ledger.get("reinvestment_partner")
            else ""
        ),
        "receipt": {
            "title": str(receipt.get("title") or ""),
            "start": str(ledger.get("start") or ""),
            "end": str(ledger.get("end") or ""),
            "sections": [_sec(s) for s in (receipt.get("sections") or [])],
        },
        "partners": [
            {
                "name": row["partner"].name,
                "share_percent": str(row.get("share_percent") or ZERO),
                "gross_entitled": str(row.get("gross_entitled") or ZERO),
                "reinvestment_cut": str(row.get("reinvestment_cut") or ZERO),
                "entitled": str(row.get("entitled") or ZERO),
                "withdrawn": str(row.get("withdrawn") or ZERO),
                "remaining": str(row.get("remaining") or ZERO),
            }
            for row in (ledger.get("rows") or [])
            if not row.get("inactive")
        ],
    }


def ledger_from_period(tenant, period: ProfitPeriod, *, hotel=None) -> dict:
    """
    Yopilgan davr: snayp bo‘lsa undan; aks holda qayta hisob (eski davrlar).
    """
    if period.ended_on and period.receipt_snapshot:
        snap = period.receipt_snapshot
        # Minimal ledger shape for templates
        receipt = snap.get("receipt") or {}
        # Rehydrate Decimal amounts in lines for money filter
        sections = []
        for sec in receipt.get("sections") or []:
            lines = []
            for line in sec.get("lines") or []:
                lines.append(
                    {
                        **line,
                        "amount": _q(line.get("amount")),
                    }
                )
            sections.append({**sec, "lines": lines})
        partners = []
        for p in snap.get("partners") or []:
            partners.append(
                {
                    "name": p.get("name"),
                    "share_percent": _q(p.get("share_percent")),
                    "gross_entitled": _q(p.get("gross_entitled")),
                    "reinvestment_cut": _q(p.get("reinvestment_cut")),
                    "entitled": _q(p.get("entitled")),
                    "withdrawn": _q(p.get("withdrawn")),
                    "remaining": _q(p.get("remaining")),
                    "from_snapshot": True,
                }
            )
        return {
            "period": period,
            "start": period.started_on,
            "end": period.ended_on,
            "net": _q(snap.get("net") or period.net_snapshot),
            "operating_net": _q(snap.get("operating_net") or period.net_snapshot),
            "reinvestment": _q(snap.get("reinvestment") or period.reinvestment_snapshot),
            "distributable": _q(
                snap.get("distributable") or period.distributable_snapshot
            ),
            "pnl": {
                "revenue_total": _q(snap.get("revenue_total") or period.revenue_snapshot),
                "operating_costs": _q(
                    snap.get("operating_costs") or period.operating_snapshot
                ),
            },
            "receipt": {**receipt, "sections": sections},
            "snapshot_partners": partners,
            "from_snapshot": True,
            "rows": [],
            "withdrawals": list(
                ProfitWithdrawal.objects.filter(tenant=tenant, period=period)
                .select_related("partner")
                .order_by("-paid_on", "-id")[:40]
            ),
        }
    return build_partner_ledger(tenant, period=period, hotel=hotel)


def build_partner_ledger(tenant, *, period: ProfitPeriod | None = None, hotel=None) -> dict:
    """
    Sof = tushum − joriy rasxod − oylik − komissiya − ombor …
    Ulushlar sof foydadan. Reinvestitsiya Sofga kirmaydi — ulushi eng katta
    sherikning ulushidan ayiriladi (qolganlar to‘liq foizini oladi).
    """
    from reports.accounting import cash_pnl_for_range, reinvestment_in_range

    period = period or ensure_open_period(tenant)
    start, end = period_bounds(period)
    pnl = cash_pnl_for_range(tenant, start, end, hotel=hotel)
    operating_net = _q(pnl["net"])
    reinvestment = _q(reinvestment_in_range(tenant, start, end, hotel=hotel))
    # net = sof foyda (ulushlar shundan); reinvest alohida — major sherikdan
    net = operating_net

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
    major = _major_share_partner(partners) if reinvestment > 0 else None
    rows = []
    entitled_total = ZERO
    withdrawn_total = ZERO
    remaining_total = ZERO
    for p in partners:
        pct = _q(p.share_percent)
        gross = _q(net * pct / HUNDRED) if net != 0 else ZERO
        reinvest_cut = _q(reinvestment) if major is not None and p.pk == major.pk else ZERO
        entitled = _q(gross - reinvest_cut)
        withdrawn = withdrawn_by_partner.get(p.pk, ZERO)
        remaining = _q(entitled - withdrawn)
        entitled_total += entitled
        withdrawn_total += withdrawn
        remaining_total += remaining
        rows.append(
            {
                "partner": p,
                "share_percent": pct,
                "gross_entitled": gross,
                "reinvestment_cut": reinvest_cut,
                "entitled": entitled,
                "withdrawn": withdrawn,
                "remaining": remaining,
                "bears_reinvestment": bool(reinvest_cut),
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
                "gross_entitled": ZERO,
                "reinvestment_cut": ZERO,
                "entitled": ZERO,
                "withdrawn": amt,
                "remaining": _q(ZERO - amt),
                "bears_reinvestment": False,
                "inactive": True,
            }
        )
        withdrawn_total += amt
        remaining_total += _q(ZERO - amt)

    entitled_total = _q(entitled_total)
    withdrawn_total = _q(withdrawn_total)
    remaining_total = _q(remaining_total)
    distributable = entitled_total
    undistributed = _q(net - sum((_q(r["gross_entitled"]) for r in rows if not r.get("inactive")), ZERO)) if net >= 0 else ZERO
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

    result = {
        "period": period,
        "start": start,
        "end": end,
        "pnl": pnl,
        "operating_net": operating_net,
        "reinvestment": reinvestment,
        "reinvestment_partner": major,
        "net": net,
        "distributable": distributable,
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
    result["receipt"] = build_profit_receipt(result)
    return result


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
    snap = serialize_ledger_snapshot(ledger)
    period.ended_on = end
    period.closed_at = timezone.now()
    period.closed_by = user
    period.note = note or period.note
    period.net_snapshot = ledger["net"]
    period.revenue_snapshot = ledger["pnl"]["revenue_total"]
    period.operating_snapshot = ledger["pnl"]["operating_costs"]
    period.reinvestment_snapshot = ledger["reinvestment"]
    period.distributable_snapshot = ledger["distributable"]
    period.receipt_snapshot = snap
    period.save(
        update_fields=[
            "ended_on",
            "closed_at",
            "closed_by",
            "note",
            "net_snapshot",
            "revenue_snapshot",
            "operating_snapshot",
            "reinvestment_snapshot",
            "distributable_snapshot",
            "receipt_snapshot",
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
