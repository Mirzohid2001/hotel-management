from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from django.db import transaction
from django.utils import timezone

from core.models import log_activity
from reports.day_lock import assert_day_open


def _folio_hotel(folio):
    res = getattr(folio, "reservation", None)
    return getattr(res, "hotel", None) if res else None

from .models import CashShift, Folio, FolioCharge, GuestPayment


@transaction.atomic
def ensure_folio_for_reservation(reservation, *, allow_pre_checkin=False) -> Folio:
    existing = Folio.objects.filter(reservation=reservation).first()
    if existing:
        return existing
    from bookings.models import Stay

    stay = Stay.objects.filter(reservation=reservation).first()
    if stay is None and not allow_pre_checkin:
        raise ValidationError(_("Mehmon hisobini ochishdan oldin joylash kerak."))
    return Folio.objects.create(
        tenant=reservation.tenant,
        reservation=reservation,
        stay=stay,
    )


@transaction.atomic
def post_room_charge(folio: Folio, user, amount: Decimal, description=None) -> FolioCharge:
    if description is None:
        description = _("Xona to‘lovi")
    if not folio.is_open:
        raise ValidationError(_("Mehmon hisobi yopilgan."))
    res = folio.reservation
    return add_charge(
        folio,
        user,
        charge_type=FolioCharge.ChargeType.ROOM,
        description=description,
        unit_price=amount,
        quantity=Decimal("1"),
        currency=getattr(res, "currency", None) or folio.tenant.currency,
    )


def night_charge_description(day) -> str:
    # Keep a stable English prefix for idempotency / legacy filters.
    return f"Night {day.isoformat()} — " + _("xona to‘lovi")


def folio_has_legacy_prepaid_room(folio: Folio) -> bool:
    """True if folio has a non-nightly room charge (old prepaid stay model)."""
    return (
        FolioCharge.objects.filter(
            folio=folio, charge_type=FolioCharge.ChargeType.ROOM, is_void=False
        )
        .exclude(description__startswith="Night ")
        .exists()  # nightly posts always start with "Night "

    )


def night_amount_for(reservation, day) -> Decimal:
    from datetime import timedelta

    from properties.services import quote_stay

    if reservation.nightly_rate is not None and reservation.nightly_rate > 0:
        return reservation.nightly_rate
    if reservation.rate_plan_id:
        return quote_stay(
            reservation.rate_plan, day, day + timedelta(days=1), adults=reservation.adults
        )
    return reservation.room_type.base_price or Decimal("0")


@transaction.atomic
def ensure_stay_nights_posted(reservation, user) -> int:
    """
    Post missing per-night room charges for [check_in, check_out).
    Skips if folio already has a legacy prepaid stay room charge.
    Returns number of nights newly posted.
    """
    from datetime import timedelta

    folio = ensure_folio_for_reservation(reservation)
    if folio_has_legacy_prepaid_room(folio):
        return 0
    posted = 0
    day = reservation.check_in
    while day < reservation.check_out:
        desc = night_charge_description(day)
        exists = FolioCharge.objects.filter(
            folio=folio,
            charge_type=FolioCharge.ChargeType.ROOM,
            description=desc,
            is_void=False,
        ).exists()
        if not exists:
            add_charge(
                folio,
                user,
                charge_type=FolioCharge.ChargeType.ROOM,
                description=desc,
                unit_price=night_amount_for(reservation, day),
                quantity=Decimal("1"),
                currency=getattr(reservation, "currency", None) or folio.tenant.currency,
            )
            posted += 1
        day = day + timedelta(days=1)
    return posted


@transaction.atomic
def add_charge(
    folio, user, *, charge_type, description, unit_price, quantity=Decimal("1"),
    currency=None, fx_rate=None,
) -> FolioCharge:
    if not folio.is_open:
        raise ValidationError(_("Mehmon hisobi yopilgan."))
    assert_day_open(folio.tenant, timezone.localdate(), user, hotel=_folio_hotel(folio))
    charge = FolioCharge(
        tenant=folio.tenant,
        folio=folio,
        charge_type=charge_type,
        description=description,
        quantity=quantity,
        unit_price=unit_price,
        posted_by=user,
        currency=currency or folio.tenant.currency or "UZS",
    )
    if fx_rate is not None:
        charge.fx_rate = fx_rate
        charge._lock_fx = True
    charge.save()
    log_activity(
        tenant=folio.tenant,
        user=user,
        action="charge_posted",
        model="FolioCharge",
        object_id=charge.pk,
        payload={
            "amount": str(charge.amount),
            "amount_base": str(charge.amount_base),
            "currency": charge.currency,
            "folio": folio.pk,
        },
    )
    return charge


@transaction.atomic
def add_payment(
    folio,
    user,
    *,
    amount,
    method=GuestPayment.Method.CASH,
    note="",
    kind=GuestPayment.Kind.PAYMENT,
    currency=None,
    fx_rate=None,
) -> GuestPayment:
    if amount <= 0:
        raise ValidationError(_("To‘lov summasi musbat bo‘lishi kerak."))
    if not folio.is_open:
        raise ValidationError(_("Mehmon hisobi yopilgan."))
    assert_day_open(folio.tenant, timezone.localdate(), user, hotel=_folio_hotel(folio))
    cash_shift = None
    if method == GuestPayment.Method.CASH and folio.tenant.has_feature("cash_shift"):
        hotel = _folio_hotel(folio)
        cash_shift = get_open_shift(folio.tenant, hotel=hotel)
        if cash_shift is None:
            raise ValidationError(
                _("Naqd to‘lovdan oldin shu filial kassa smenasini oching.")
            )
    payment = GuestPayment(
        tenant=folio.tenant,
        folio=folio,
        amount=amount,
        method=method,
        kind=kind or GuestPayment.Kind.PAYMENT,
        note=note,
        received_by=user,
        cash_shift=cash_shift,
        currency=currency or folio.tenant.currency or "UZS",
    )
    if fx_rate is not None:
        payment.fx_rate = fx_rate
        payment._lock_fx = True
    payment.save()
    log_activity(
        tenant=folio.tenant,
        user=user,
        action="payment_received",
        model="GuestPayment",
        object_id=payment.pk,
        payload={
            "amount": str(amount),
            "amount_base": str(payment.amount_base),
            "currency": payment.currency,
            "method": method,
            "folio": folio.pk,
        },
    )
    return payment


@transaction.atomic
def void_charge(charge: FolioCharge, user, *, reason: str = "") -> FolioCharge:
    if charge.is_void:
        raise ValidationError(_("Yozuv allaqachon bekor qilingan."))
    if not charge.folio.is_open:
        raise ValidationError(_("Yopilgan hisobda bekor qilib bo‘lmaydi."))
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError(_("Bekor qilish sababi kerak."))
    assert_day_open(
        charge.tenant, timezone.localdate(), user, hotel=_folio_hotel(charge.folio)
    )
    charge.is_void = True
    charge.void_reason = reason
    charge.voided_at = timezone.now()
    charge.voided_by = user
    charge.save(
        update_fields=["is_void", "void_reason", "voided_at", "voided_by", "updated_at"]
    )
    log_activity(
        tenant=charge.tenant,
        user=user,
        action="charge_voided",
        model="FolioCharge",
        object_id=charge.pk,
        payload={"reason": reason},
    )
    return charge


@transaction.atomic
def void_payment(payment: GuestPayment, user, *, reason: str = "") -> GuestPayment:
    if payment.is_void:
        raise ValidationError(_("To‘lov allaqachon bekor qilingan."))
    if not payment.folio.is_open:
        raise ValidationError(_("Yopilgan hisobda bekor qilib bo‘lmaydi."))
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError(_("Bekor qilish sababi kerak."))
    assert_day_open(
        payment.tenant, timezone.localdate(), user, hotel=_folio_hotel(payment.folio)
    )
    payment.is_void = True
    payment.void_reason = reason
    payment.voided_at = timezone.now()
    payment.voided_by = user
    payment.save(
        update_fields=["is_void", "void_reason", "voided_at", "voided_by", "updated_at"]
    )
    log_activity(
        tenant=payment.tenant,
        user=user,
        action="payment_voided",
        model="GuestPayment",
        object_id=payment.pk,
        payload={"reason": reason},
    )
    return payment


@transaction.atomic
def add_split_payments(folio, user, lines: list[dict]) -> list[GuestPayment]:
    """Post several payments/deposits in one transaction (split tender)."""
    if not lines:
        raise ValidationError(_("Kamida bitta to‘lov qatorini qo‘shing."))
    created = []
    for line in lines:
        amount = line.get("amount")
        if amount is None or amount <= 0:
            continue
        created.append(
            add_payment(
                folio,
                user,
                amount=amount,
                method=line.get("method") or GuestPayment.Method.CASH,
                note=line.get("note") or "",
                kind=line.get("kind") or GuestPayment.Kind.PAYMENT,
                currency=line.get("currency"),
                fx_rate=line.get("fx_rate"),
            )
        )
    if not created:
        raise ValidationError(_("Summali kamida bitta to‘lov qatorini qo‘shing."))
    return created


@transaction.atomic
def open_folio_for_deposit(reservation, user) -> Folio:
    """Open folio before check-in so deposit can be taken."""
    return ensure_folio_for_reservation(reservation, allow_pre_checkin=True)


EMEHMON_MARKER = "E-mehmon"
EMEHMON_LEGACY_MARKERS = ("E-mehmon", "Emehmon", "e-mehmon")
DEFAULT_EMEHMON_UNIT = Decimal("9000")


def emehmon_guest_count(adults=None, children=None) -> int:
    """Ro‘yxatdan o‘tadigan mehmonlar soni (kamida 1)."""
    a = int(adults or 0)
    c = int(children or 0)
    return max(1, a + c)


def emehmon_nights_count(nights=None, *, check_in=None, check_out=None) -> int:
    if nights is not None:
        try:
            return max(1, int(nights))
        except (TypeError, ValueError):
            return 1
    if check_in and check_out:
        days = (check_out - check_in).days
        return max(1, days)
    return 1


def calc_emehmon_fee(unit_rate, *, nights: int = 1, guests: int = 1) -> Decimal:
    """1 mehmon × 1 kecha × tarif = jami E-mehmon komissiyasi."""
    unit = Decimal(unit_rate or 0)
    if unit <= 0:
        return Decimal("0")
    n = max(1, int(nights or 1))
    g = max(1, int(guests or 1))
    return (unit * n * g).quantize(Decimal("0.01"))


def emehmon_unit_rate(hotel) -> Decimal:
    """Mehmonxona sozlamasidagi 1 mehmon/1 kecha tarif (so‘m)."""
    from properties.models import PropertySettings

    if hotel is None:
        return Decimal("0")
    hotel_id = hotel.pk if hasattr(hotel, "pk") else hotel
    settings = PropertySettings.objects.filter(property_id=hotel_id).first()
    if not settings:
        return Decimal("0")
    return settings.emehmon_fee or Decimal("0")


def default_emehmon_fee(reservation) -> Decimal:
    """Bron uchun jami: tarif × kechalar × mehmonlar."""
    unit = emehmon_unit_rate(getattr(reservation, "hotel_id", None) or getattr(reservation, "hotel", None))
    nights = emehmon_nights_count(getattr(reservation, "nights", None))
    guests = emehmon_guest_count(
        getattr(reservation, "adults", None),
        getattr(reservation, "children", None),
    )
    return calc_emehmon_fee(unit, nights=nights, guests=guests)


def emehmon_already_posted(folio) -> bool:
    from django.db.models import Q

    already = Q(charge_type=FolioCharge.ChargeType.EMEHMON)
    for prefix in EMEHMON_LEGACY_MARKERS:
        already |= Q(description__startswith=prefix)
    return folio.charges.filter(already, is_void=False).exists()


@transaction.atomic
def collect_emehmon_fee(
    reservation,
    user,
    *,
    amount=None,
    method=GuestPayment.Method.CASH,
    note="",
    currency=None,
    fx_rate=None,
) -> tuple[FolioCharge, GuestPayment]:
    """Post E-mehmon charge (once) and take payment — bron/kirish paytida."""
    unit = emehmon_unit_rate(reservation.hotel_id)
    nights = emehmon_nights_count(getattr(reservation, "nights", None))
    guests = emehmon_guest_count(reservation.adults, reservation.children)
    computed = calc_emehmon_fee(unit, nights=nights, guests=guests)
    if amount is None:
        fee = computed
        use_breakdown = unit > 0 and computed > 0
    else:
        fee = amount
        use_breakdown = (
            unit > 0 and computed > 0 and fee == computed
        )
    if fee is None or fee <= 0:
        raise ValidationError(_("E-mehmon summasi musbat bo‘lishi kerak."))

    folio = ensure_folio_for_reservation(reservation, allow_pre_checkin=True)
    if emehmon_already_posted(folio):
        raise ValidationError(_("E-mehmon to‘lovi allaqachon yozilgan."))

    cur = currency or folio.tenant.currency or "UZS"
    if use_breakdown:
        qty = Decimal(nights * guests)
        unit_price = unit
        description = _(
            "E-mehmon: %(g)s mehmon × %(n)s kecha × %(u)s"
        ) % {"g": guests, "n": nights, "u": unit}
    else:
        qty = Decimal("1")
        unit_price = fee
        description = _("E-mehmon: ro‘yxatdan o‘tkazish")

    charge = add_charge(
        folio,
        user,
        charge_type=FolioCharge.ChargeType.EMEHMON,
        description=description,
        unit_price=unit_price,
        quantity=qty,
        currency=cur,
        fx_rate=fx_rate,
    )
    payment_note = (note or "").strip() or _("E-mehmon to‘lovi")
    # Naqd P&L tushumdan chiqarish uchun marker majburiy
    if not any(m.lower() in payment_note.lower() for m in EMEHMON_LEGACY_MARKERS):
        payment_note = f"{EMEHMON_MARKER}: {payment_note}"
    payment = add_payment(
        folio,
        user,
        amount=fee,
        method=method,
        note=payment_note,
        kind=GuestPayment.Kind.PAYMENT,
        currency=cur,
        fx_rate=fx_rate,
    )
    if not reservation.emehmon_required:
        reservation.emehmon_required = True
        reservation.save(update_fields=["emehmon_required", "updated_at"])
    return charge, payment


@transaction.atomic
def close_folio(folio: Folio) -> Folio:
    if folio.balance != 0:
        raise ValidationError(
            _("Qoldiq %(b)s bo‘lgan mehmon hisobini yopib bo‘lmaydi.") % {"b": folio.balance}
        )
    folio.is_open = False
    folio.closed_at = timezone.now()
    folio.save(update_fields=["is_open", "closed_at", "updated_at"])
    return folio


def get_open_shift(tenant, hotel=None) -> CashShift | None:
    qs = CashShift.objects.filter(tenant=tenant, closed_at__isnull=True)
    if hotel is not None:
        qs = qs.filter(hotel=hotel)
    return qs.first()


def expected_cash_in_shift(shift: CashShift) -> Decimal:
    from .shift_report import build_shift_report

    return build_shift_report(shift)["expected_cash"]


@transaction.atomic
def open_cash_shift(
    tenant, user, opening_float: Decimal = Decimal("0"), *, hotel=None
) -> CashShift:
    if hotel is None:
        raise ValidationError(_("Kassa smenasi uchun filial tanlang."))
    if get_open_shift(tenant, hotel=hotel):
        raise ValidationError(_("Bu filialda ochiq kassa smenasi allaqachon bor."))
    return CashShift.objects.create(
        tenant=tenant,
        hotel=hotel,
        opened_by=user,
        opening_float=opening_float or Decimal("0"),
    )


@transaction.atomic
def add_cash_movement(
    shift: CashShift,
    user,
    *,
    kind: str,
    amount: Decimal,
    note: str = "",
    currency: str | None = None,
    fx_rate=None,
):
    from .models import CashShiftMovement

    if not shift.is_open:
        raise ValidationError(_("Faqat ochiq smenaga harakat qo‘shiladi."))
    amount = Decimal(amount or 0)
    if amount <= 0:
        raise ValidationError(_("Summa 0 dan katta bo‘lishi kerak."))
    if kind not in dict(CashShiftMovement.Kind.choices):
        raise ValidationError(_("Noto‘g‘ri harakat turi."))
    movement = CashShiftMovement(
        tenant=shift.tenant,
        shift=shift,
        kind=kind,
        amount=amount,
        note=(note or "").strip()[:255],
        created_by=user,
        currency=currency or shift.tenant.currency or "UZS",
    )
    if fx_rate is not None:
        movement.fx_rate = fx_rate
        movement._lock_fx = True
    movement.save()
    log_activity(
        tenant=shift.tenant,
        user=user,
        action="cash_shift_movement",
        model="CashShiftMovement",
        object_id=movement.pk,
        payload={
            "shift": shift.pk,
            "kind": kind,
            "amount": str(amount),
            "amount_base": str(movement.amount_base),
            "currency": movement.currency,
            "note": movement.note,
        },
    )
    return movement


@transaction.atomic
def close_cash_shift(
    shift: CashShift, user, closing_cash: Decimal, notes: str = ""
) -> CashShift:
    if not shift.is_open:
        raise ValidationError(_("Smena allaqachon yopilgan."))
    expected = expected_cash_in_shift(shift)
    shift.closed_at = timezone.now()
    shift.closed_by = user
    shift.closing_cash = closing_cash
    shift.variance = closing_cash - expected
    shift.notes = notes
    shift.save(
        update_fields=[
            "closed_at",
            "closed_by",
            "closing_cash",
            "variance",
            "notes",
            "updated_at",
        ]
    )
    log_activity(
        tenant=shift.tenant,
        user=user,
        action="cash_shift_closed",
        model="CashShift",
        object_id=shift.pk,
        payload={
            "expected": str(expected),
            "closing": str(closing_cash),
            "variance": str(shift.variance),
        },
    )
    return shift
