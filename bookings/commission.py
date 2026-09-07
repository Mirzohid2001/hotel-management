from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from folio.models import FolioCharge

from .models import BookingReferrer, ReferrerCommissionPayment, Reservation


def reservation_commission_base(reservation: Reservation) -> Decimal:
    """Room revenue in tenant base currency: posted ROOM charges if any, else quote."""
    from core.currency import to_base_amount

    folio = getattr(reservation, "folio", None)
    if folio is not None:
        total = (
            folio.charges.filter(
                is_void=False, charge_type=FolioCharge.ChargeType.ROOM
            ).aggregate(s=Sum("amount_base"))["s"]
            or Decimal("0")
        )
        if total > 0:
            return total
    raw = reservation.total_amount or Decimal("0")
    if raw <= 0:
        return Decimal("0")
    _c, _r, base = to_base_amount(
        reservation.tenant,
        raw,
        getattr(reservation, "currency", None) or reservation.tenant.currency,
    )
    return base


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

    report = build_commission_report(tenant, year=year, month=month)
    group = next((g for g in report["groups"] if g["referrer"].pk == referrer.pk), None)
    owed = group["commission_total"] if group else Decimal("0")
    paid = paid_total_for_period(tenant, year=year, month=month, referrer_id=referrer.pk)
    remaining = owed - paid
    if not allow_overpay and amount > remaining:
        raise ValidationError(
            _("Qolgan summadan ko‘p: qolgan %(r)s, so‘ralgan %(a)s.")
            % {"r": remaining, "a": amount}
        )

    return ReferrerCommissionPayment.objects.create(
        tenant=tenant,
        referrer=referrer,
        year=year,
        month=month,
        amount=amount,
        currency=currency or tenant.currency or "UZS",
        paid_on=paid_on or timezone.localdate(),
        method=method,
        note=(note or "").strip(),
        created_by=user,
    )


def build_commission_report(tenant, *, year: int, month: int) -> dict:
    """
    Monthly commission by referrer for stays whose check-out falls in the month.
    Excludes cancelled / no-show. Includes paid / remaining per referrer.
    """
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    qs = (
        Reservation.objects.filter(
            tenant=tenant,
            referrer__isnull=False,
            check_out__gte=start,
            check_out__lte=end,
        )
        .exclude(
            status__in=[
                Reservation.Status.CANCELLED,
                Reservation.Status.NO_SHOW,
            ]
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
