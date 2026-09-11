from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from folio.models import FolioCharge
from folio.services import charge_amount_base, deduped_night_room_total

from .models import BookingReferrer, ReferrerCommissionPayment, Reservation


def reservation_commission_base(reservation: Reservation) -> Decimal:
    """
    Xona tushumi (bazaviy valyuta) — komissiya foizi shu asosdan.

    Tartib:
    1) «Night …» xona yozuvlari (kecha bo‘yicha dedupe)
    2) Eski uslubdagi bir martalik ROOM (faqat bron summasiga yaqin bo‘lsa)
    3) Bronning total_amount (quote)

    Agar Night yig‘indisi bron summasidan katta bo‘lsa (ikkalangan yozuv) —
    bron summasi olinadi. Minibar/xizmat bazaga kirmaydi.
    """
    from core.currency import to_base_amount

    raw = reservation.total_amount or Decimal("0")
    quote = Decimal("0")
    if raw > 0:
        _c, _r, quote = to_base_amount(
            reservation.tenant,
            raw,
            getattr(reservation, "currency", None) or reservation.tenant.currency,
        )

    folio = getattr(reservation, "folio", None)
    if folio is not None:
        night_total = deduped_night_room_total(folio)
        if night_total > 0:
            if quote > 0 and night_total > quote:
                return quote
            return night_total

        other_total = Decimal("0")
        for charge in folio.charges.filter(
            is_void=False, charge_type=FolioCharge.ChargeType.ROOM
        ).exclude(description__startswith="Night "):
            other_total += charge_amount_base(charge)
        # Prepaid/legacy stay: faqat bron narxining kamida yarmini qoplasa
        if other_total > 0 and (quote <= 0 or other_total >= quote * Decimal("0.5")):
            if quote > 0 and other_total > quote:
                return quote
            return other_total

    return quote


def reservation_commission_amount(reservation: Reservation) -> Decimal:
    if not reservation.referrer_id:
        return Decimal("0")
    percent = reservation.commission_percent
    if percent is None:
        return Decimal("0")
    base = reservation_commission_base(reservation)
    return (base * Decimal(percent) / Decimal("100")).quantize(Decimal("0.01"))


def payments_for_period(tenant, *, year: int, month: int, referrer_id=None):
    qs = ReferrerCommissionPayment.objects.filter(
        tenant=tenant, year=year, month=month
    ).select_related("referrer")
    if referrer_id is not None:
        qs = qs.filter(referrer_id=referrer_id)
    return qs


def paid_total_for_period(tenant, *, year: int, month: int, referrer_id=None) -> Decimal:
    qs = payments_for_period(tenant, year=year, month=month, referrer_id=referrer_id)
    return qs.aggregate(s=Sum("amount_base"))["s"] or Decimal("0")


@transaction.atomic
def record_commission_payment(
    tenant,
    referrer: BookingReferrer,
    *,
    year: int,
    month: int,
    amount: Decimal,
    paid_on=None,
    method: str = ReferrerCommissionPayment.Method.CASH,
    note: str = "",
    user=None,
    allow_overpay: bool = False,
    currency: str | None = None,
) -> ReferrerCommissionPayment:
    if referrer.tenant_id != tenant.pk:
        raise ValidationError(_("Yo‘naltiruvchi ushbu mehmonxonaga tegishli emas."))
    amount = Decimal(amount)
    if amount <= 0:
        raise ValidationError(_("Summa musbat bo‘lishi kerak."))

    from core.currency import to_base_amount

    pay_currency = currency or tenant.currency or "UZS"
    report = build_commission_report(tenant, year=year, month=month)
    group = next((g for g in report["groups"] if g["referrer"].pk == referrer.pk), None)
    owed = group["commission_total"] if group else Decimal("0")
    paid = paid_total_for_period(tenant, year=year, month=month, referrer_id=referrer.pk)
    remaining = owed - paid
    _cur, _rate, amount_base = to_base_amount(tenant, amount, pay_currency)
    if not allow_overpay and amount_base > remaining:
        raise ValidationError(
            _("Qolgan summadan ko‘p: qolgan %(r)s %(cur)s, so‘ralgan %(a)s %(pay)s.")
            % {
                "r": remaining,
                "cur": tenant.currency or "UZS",
                "a": amount,
                "pay": pay_currency,
            }
        )

    return ReferrerCommissionPayment.objects.create(
        tenant=tenant,
        referrer=referrer,
        year=year,
        month=month,
        amount=amount,
        currency=pay_currency,
        paid_on=paid_on or timezone.localdate(),
        method=method,
        note=(note or "").strip(),
        created_by=user,
    )


def build_commission_report(tenant, *, year: int, month: int) -> dict:
    """
    Monthly commission by referrer for stays whose check-out falls in the month.
    Faqat CHECKED_OUT — Sof/P&L komissiyasi bilan bir xil.
    """
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    qs = (
        Reservation.objects.filter(
            tenant=tenant,
            referrer__isnull=False,
            status=Reservation.Status.CHECKED_OUT,
            check_out__gte=start,
            check_out__lte=end,
        )
        .select_related("referrer", "guest", "room", "hotel")
        .prefetch_related("folio__charges")
        .order_by("referrer__name", "check_out", "code")
    )

    by_referrer: dict[int, dict] = {}
    rows = []
    grand_base = Decimal("0")
    grand_commission = Decimal("0")

    for res in qs:
        base = reservation_commission_base(res)
        amount = reservation_commission_amount(res)
        percent = res.commission_percent or Decimal("0")
        row = {
            "reservation": res,
            "base": base,
            "percent": percent,
            "commission": amount,
        }
        rows.append(row)
        grand_base += base
        grand_commission += amount
        ref = res.referrer
        bucket = by_referrer.setdefault(
            ref.pk,
            {
                "referrer": ref,
                "count": 0,
                "base_total": Decimal("0"),
                "commission_total": Decimal("0"),
                "rows": [],
            },
        )
        bucket["count"] += 1
        bucket["base_total"] += base
        bucket["commission_total"] += amount
        bucket["rows"].append(row)

    payments = list(payments_for_period(tenant, year=year, month=month))
    paid_by_ref: dict[int, Decimal] = {}
    payments_by_ref: dict[int, list] = {}
    for p in payments:
        paid_by_ref[p.referrer_id] = paid_by_ref.get(p.referrer_id, Decimal("0")) + (
            p.amount_base or p.amount
        )
        payments_by_ref.setdefault(p.referrer_id, []).append(p)

    # Include referrers who were paid but have no bookings this month
    for rid, paid_amt in paid_by_ref.items():
        if rid not in by_referrer:
            ref = next((p.referrer for p in payments if p.referrer_id == rid), None)
            if ref is None:
                continue
            by_referrer[rid] = {
                "referrer": ref,
                "count": 0,
                "base_total": Decimal("0"),
                "commission_total": Decimal("0"),
                "rows": [],
            }

    grand_paid = Decimal("0")
    grand_remaining = Decimal("0")
    for bucket in by_referrer.values():
        rid = bucket["referrer"].pk
        paid = paid_by_ref.get(rid, Decimal("0"))
        remaining = bucket["commission_total"] - paid
        bucket["paid_total"] = paid
        bucket["remaining"] = remaining
        bucket["payments"] = payments_by_ref.get(rid, [])
        grand_paid += paid
        grand_remaining += remaining

    groups = sorted(by_referrer.values(), key=lambda g: g["referrer"].name.lower())
    return {
        "year": year,
        "month": month,
        "start": start,
        "end": end,
        "groups": groups,
        "rows": rows,
        "grand_base": grand_base,
        "grand_commission": grand_commission,
        "grand_paid": grand_paid,
        "grand_remaining": grand_remaining,
        "referrer_count": len(groups),
        "reservation_count": len(rows),
    }


def active_referrers(tenant):
    return BookingReferrer.objects.filter(tenant=tenant, is_active=True)
