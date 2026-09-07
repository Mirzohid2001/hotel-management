"""E-mehmon oylik komissiya hisoboti — mehmon × kecha × tarif."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone

from folio.models import FolioCharge
from folio.services import (
    calc_emehmon_fee,
    emehmon_already_posted,
    emehmon_guest_count,
)
from properties.models import PropertySettings

from .models import Reservation


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return start, end


def nights_overlap(check_in: date, check_out: date, start: date, end: date) -> int:
    """Davr ichidagi kechalar (check_out kuni hisoblanmaydi)."""
    if not check_in or not check_out or check_out <= check_in:
        return 0
    stay_start = max(check_in, start)
    stay_end = min(check_out, end + timedelta(days=1))
    if stay_end <= stay_start:
        return 0
    return (stay_end - stay_start).days


def emehmon_totals_for_range(
    tenant,
    start: date,
    end: date,
    *,
    hotel=None,
    realized_only: bool = False,
) -> dict:
    """
    Davr uchun E-mehmon jami.

    realized_only=True — faqat boshlangan/yashagan bronlar (P&L uchun).
    """
    qs = (
        Reservation.objects.filter(tenant=tenant)
        .exclude(status=Reservation.Status.CANCELLED)
        .exclude(status=Reservation.Status.NO_SHOW)
        .filter(check_in__lte=end, check_out__gt=start)
        .select_related("guest", "hotel", "folio")
        .order_by("check_in", "pk")
    )
    if hotel is not None:
        qs = qs.filter(hotel=hotel)
    if realized_only:
        today = timezone.localdate()
        qs = qs.filter(
            Q(status__in=[Reservation.Status.CHECKED_IN, Reservation.Status.CHECKED_OUT])
            | Q(
                status=Reservation.Status.CONFIRMED,
                check_in__lte=min(end, today),
            )
        )

    settings_map = {
        s.property_id: s.emehmon_fee or Decimal("0")
        for s in PropertySettings.objects.filter(tenant=tenant)
    }

    rows = []
    total_guest_nights = 0
    total_expected = Decimal("0")
    total_collected = Decimal("0")

    for res in qs:
        unit = settings_map.get(res.hotel_id, Decimal("0"))
        guests = emehmon_guest_count(res.adults, res.children)
        nights = nights_overlap(res.check_in, res.check_out, start, end)
        if nights <= 0:
            continue
        guest_nights = nights * guests
        collected_full = Decimal("0")
        folio = getattr(res, "folio", None)
        if folio is not None:
            collected_full = (
                folio.charges.filter(
                    is_void=False, charge_type=FolioCharge.ChargeType.EMEHMON
                ).aggregate(s=Sum("amount_base"))["s"]
                or Decimal("0")
            )
        # Ko‘p oylik bron: olingan summani kechalar ulushiga bo‘lamiz
        stay_nights = max(1, int(getattr(res, "nights", None) or nights))
        collected = (
            (collected_full * Decimal(nights) / Decimal(stay_nights)).quantize(
                Decimal("0.01")
            )
            if collected_full
            else Decimal("0")
        )
        # Ixtiyoriy: faqat belgilangan bronlarda to‘liq kutilgan summa.
        # Belgilanmagan, lekin biror to‘lov bor — kutilgan = olingan (farq 0).
        required = bool(getattr(res, "emehmon_required", False))
        if required:
            expected = calc_emehmon_fee(unit, nights=nights, guests=guests)
            applies = True
        elif collected_full > 0:
            expected = collected
            applies = True
        else:
            expected = Decimal("0")
            applies = False
            guest_nights = 0

        posted = bool(folio and emehmon_already_posted(folio))

        total_guest_nights += guest_nights
        total_expected += expected
        total_collected += collected

        rows.append(
            {
                "reservation": res,
                "guest_name": str(res.guest) if res.guest_id else "—",
                "hotel_name": res.hotel.name if res.hotel_id else "—",
                "check_in": res.check_in,
                "check_out": res.check_out,
                "guests": guests,
                "nights_in_month": nights,
                "guest_nights": guest_nights,
                "unit": unit,
                "expected": expected,
                "collected": collected,
                "collected_full": collected_full,
                "posted": posted,
                "applies": applies,
                "required": required,
                "gap": expected - collected,
            }
        )

    charge_qs = FolioCharge.objects.filter(
        tenant=tenant,
        is_void=False,
        charge_type=FolioCharge.ChargeType.EMEHMON,
        created_at__date__gte=start,
        created_at__date__lte=end,
    )
    if hotel is not None:
        charge_qs = charge_qs.filter(folio__reservation__hotel=hotel)
    posted_in_period = charge_qs.aggregate(s=Sum("amount_base"))["s"] or Decimal("0")

    gap = total_expected - total_collected
    shortfall = max(Decimal("0"), gap)

    return {
        "start": start,
        "end": end,
        "rows": rows,
        "total_guest_nights": total_guest_nights,
        "total_expected": total_expected,
        "total_collected": total_collected,
        "total_gap": gap,
        "shortfall": shortfall,
        "posted_in_period": posted_in_period,
        "default_unit": Decimal("9000"),
    }


def build_emehmon_report(tenant, *, year: int, month: int, hotel=None) -> dict:
    """
    Oylik E-mehmon:
    - hisoblangan: oy ichidagi mehmon-kechalar × tarif (E-mehmonga berilishi kerak)
    - olingan: folio dagi EMEHMON charge (mehmondan)
    """
    start, end = _month_bounds(year, month)
    data = emehmon_totals_for_range(tenant, start, end, hotel=hotel, realized_only=False)
    return {
        "year": year,
        "month": month,
        **data,
        "posted_in_month": data["posted_in_period"],
    }


def emehmon_shortfall_for_range(
    tenant, start: date, end: date, *, hotel=None
) -> Decimal:
    """P&L rasxodi: hisoblangan − mehmondan olingan (kamida 0)."""
    data = emehmon_totals_for_range(
        tenant, start, end, hotel=hotel, realized_only=True
    )
    return data["shortfall"]
