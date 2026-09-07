from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils.translation import gettext as _

from .models import Property, RatePlan, RoomType, SeasonRate
from .room_type_presets import (
    DEFAULT_BASE_PRICE,
    LEGACY_ROOM_TYPE_REMAP,
    STANDARD_ROOM_TYPE_CODES,
    STANDARD_ROOM_TYPE_PRESETS,
)


def price_for_date(rate_plan: RatePlan, day: date) -> Decimal:
    season = (
        SeasonRate.objects.filter(
            rate_plan=rate_plan,
            date_from__lte=day,
            date_to__gte=day,
        )
        .order_by("-date_from")
        .first()
    )
    if season:
        return season.price
    return rate_plan.price


def season_name_for_date(rate_plan: RatePlan, day: date) -> str:
    season = (
        SeasonRate.objects.filter(
            rate_plan=rate_plan,
            date_from__lte=day,
            date_to__gte=day,
        )
        .order_by("-date_from")
        .first()
    )
    return season.name if season else ""


def build_rate_matrix(rate_plan: RatePlan, start: date, days: int = 42) -> list[dict]:
    """Daily price grid for rate matrix UI."""
    rows = []
    for i in range(days):
        day = start + timedelta(days=i)
        season = season_name_for_date(rate_plan, day)
        rows.append(
            {
                "date": day,
                "price": price_for_date(rate_plan, day),
                "season": season,
                "is_season": bool(season),
                "weekday": day.weekday(),
            }
        )
    return rows


def quote_stay(rate_plan: RatePlan, check_in: date, check_out: date, adults: int = 1) -> Decimal:
    """Sum nightly rates for [check_in, check_out)."""
    if check_out <= check_in:
        return Decimal("0")
    total = Decimal("0")
    day = check_in
    while day < check_out:
        night = price_for_date(rate_plan, day)
        extra = max(adults - 1, 0) * rate_plan.extra_adult_price
        total += night + extra
        day += timedelta(days=1)
    return total


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def suggest_base_price(prop: Property) -> Decimal:
    existing = (
        RoomType.objects.filter(property=prop, is_active=True)
        .exclude(base_price=0)
        .values_list("base_price", flat=True)
    )
    if existing:
        # Double/Twin factor = 1.0 — mediana yoki o‘rtacha
        prices = sorted(existing)
        mid = prices[len(prices) // 2]
        return _round_money(Decimal(mid))
    return DEFAULT_BASE_PRICE


def missing_room_type_presets(prop: Property) -> list[dict]:
    existing = set(
        RoomType.objects.filter(property=prop).values_list("code", flat=True)
    )
    return [p for p in STANDARD_ROOM_TYPE_PRESETS if p["code"] not in existing]


@transaction.atomic
def seed_standard_room_types(
    *,
    tenant,
    prop: Property,
    base_price: Decimal | None = None,
    with_rate_plans: bool = True,
) -> dict:
    """
    Yetishmayotgan standart xona turlarini yaratadi.
    Mavjud kodlar o‘zgartirilmaydi.
    """
    base = base_price if base_price is not None else suggest_base_price(prop)
    currency = getattr(tenant, "currency", None) or "UZS"
    if base <= 0:
        base = DEFAULT_BASE_PRICE

    created_types: list[RoomType] = []
    created_rates: list[RatePlan] = []
    skipped = 0

    for preset in STANDARD_ROOM_TYPE_PRESETS:
        code = preset["code"]
        if RoomType.objects.filter(property=prop, code=code).exists():
            skipped += 1
            continue

        price = _round_money(base * preset["price_factor"])
        display_name = f"{str(preset['name'])} · {preset['name_uz']}"
        rt = RoomType.objects.create(
            tenant=tenant,
            property=prop,
            name=display_name,
            code=code,
            capacity_adults=preset["capacity_adults"],
            capacity_children=preset["capacity_children"],
            base_price=price,
            currency=currency,
            description=str(preset["description"]),
            is_active=True,
        )
        created_types.append(rt)

        if with_rate_plans:
            rate_code = f"bar-{code}"[:40]
            if not RatePlan.objects.filter(property=prop, code=rate_code).exists():
                rate = RatePlan.objects.create(
                    tenant=tenant,
                    property=prop,
                    room_type=rt,
                    name=_("BAR · %(type)s") % {"type": str(preset["name"])},
                    code=rate_code,
                    price=price,
                    currency=currency,
                    is_default=True,
                )
                created_rates.append(rate)

    return {
        "created_types": created_types,
        "created_rates": created_rates,
        "skipped": skipped,
        "base_price": base,
    }


@transaction.atomic
def prune_to_standard_room_types(*, prop: Property) -> dict:
    """
    Faqat Double/Twin/Triple faol qoladi.
    Eski turlardagi xonalar yaqin standartga o‘tkaziladi, keyin eski turlar o‘chiriladi (faolsiz).
    """
    from .models import Room

    ensured = seed_standard_room_types(
        tenant=prop.tenant, prop=prop, with_rate_plans=True
    )
    by_code = {
        rt.code: rt
        for rt in RoomType.objects.filter(property=prop, code__in=STANDARD_ROOM_TYPE_CODES)
    }
    remapped_rooms = 0
    deactivated = []

    extras = RoomType.objects.filter(property=prop).exclude(code__in=STANDARD_ROOM_TYPE_CODES)
    for rt in extras:
        target_code = LEGACY_ROOM_TYPE_REMAP.get(rt.code, "double")
        target = by_code.get(target_code) or by_code.get("double")
        if target is None:
            continue
        updated = Room.objects.filter(room_type=rt).update(room_type=target)
        remapped_rooms += updated
        if rt.is_active:
            rt.is_active = False
            rt.save(update_fields=["is_active", "updated_at"])
            deactivated.append(rt.code)

    return {
        "ensured_types": [t.code for t in ensured["created_types"]],
        "remapped_rooms": remapped_rooms,
        "deactivated": deactivated,
    }
