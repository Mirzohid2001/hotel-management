from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from django.db import transaction
from django.utils import timezone

from core.models import log_activity
from properties.models import RatePlan, Room
from properties.services import quote_stay

from .models import Reservation, ReservationChangeLog, ReservationGroup, Stay


class AvailabilityError(ValidationError):
    pass


class DirtyRoomError(ValidationError):
    """Room is dirty/cleaning; check-in needs allow_dirty=True override."""


class MissingGuestDocsError(ValidationError):
    """Guest has no ID document; check-in needs allow_no_docs=True override."""


ROOM_NOT_READY_FOR_CHECKIN = frozenset(
    {
        Room.Status.DIRTY,
        Room.Status.CLEANING,
    }
)


def guest_has_id_document(guest) -> bool:
    if guest is None:
        return False
    from guests.models import GuestDocument

    return guest.documents.filter(
        doc_type__in=[GuestDocument.DocType.PASSPORT, GuestDocument.DocType.ID_CARD]
    ).exists()


def generate_reservation_code(tenant, property_obj, on_date: date | None = None) -> str:
    day = on_date or timezone.localdate()
    branch = (getattr(property_obj, "branch_code", None) or "HTL").upper()
    prefix = f"{branch}-{day.year}-"
    last = (
        Reservation.objects.filter(tenant=tenant, code__startswith=prefix)
        .order_by("-code")
        .values_list("code", flat=True)
        .first()
    )
    if last:
        try:
            n = int(last.split("-")[-1]) + 1
        except ValueError:
            n = 1
    else:
        n = 1
    return f"{prefix}{n:04d}"


def assert_room_available(room, check_in, check_out, *, exclude_reservation_id=None):
    """Date conflict on [check_in, check_out). Checkout day is bookable."""
    if room is None:
        return
    if not room.is_active:
        raise AvailabilityError(_("Xona faol emas."))
    if room.status == Room.Status.OUT_OF_ORDER:
        raise AvailabilityError(_("Xona nosoz."))
    conflict = (
        Reservation.objects.filter(tenant=room.tenant)
        .overlapping(check_in, check_out, room=room, exclude_pk=exclude_reservation_id)
        .exists()
    )
    if conflict:
        raise AvailabilityError(_("Tanlangan sanalarda xona band."))


def assert_room_physically_free(room, *, exclude_reservation_id=None):
    """Block immediate check-in while another guest is still checked in."""
    if room is None:
        return
    if (
        Reservation.objects.filter(tenant=room.tenant)
        .checked_in_on_room(room=room, exclude_pk=exclude_reservation_id)
        .exists()
    ):
        raise AvailabilityError(
            _("Xonada hali mehmon bor — avval chiqish qiling, keyin yangi mehmonni joylashtiring.")
        )


def recompute_total(reservation: Reservation) -> Decimal:
    nights = max(0, reservation.nights)
    if reservation.nightly_rate is not None and reservation.nightly_rate > 0:
        return (reservation.nightly_rate * nights).quantize(Decimal("0.01"))
    if reservation.rate_plan_id:
        return quote_stay(
            reservation.rate_plan,
            reservation.check_in,
            reservation.check_out,
            adults=reservation.adults,
        )
    return (reservation.room_type.base_price or Decimal("0")) * nights


def room_nightly_price(reservation: Reservation) -> Decimal:
    """Folio / hisobot uchun 1 kecha narxi."""
    if reservation.nightly_rate is not None and reservation.nightly_rate > 0:
        return reservation.nightly_rate
    if reservation.rate_plan_id:
        from datetime import timedelta

        from properties.services import quote_stay

        day = reservation.check_in
        return quote_stay(
            reservation.rate_plan, day, day + timedelta(days=1), adults=reservation.adults
        )
    return reservation.room_type.base_price or Decimal("0")


def log_change(reservation, user, field, old, new, reason=""):
    return ReservationChangeLog.objects.create(
        tenant=reservation.tenant,
        reservation=reservation,
        user=user,
        field=field,
        old_value=str(old) if old is not None else "",
        new_value=str(new) if new is not None else "",
        reason=reason,
    )


@transaction.atomic
def create_reservation(
    *,
    tenant,
    user,
    property_obj,
    guest,
    room_type,
    check_in,
    check_out,
    room=None,
    rate_plan=None,
    nightly_rate=None,
    currency=None,
    adults=1,
    children=0,
    source=Reservation.Source.PHONE,
    notes="",
    company=None,
    group=None,
    status=Reservation.Status.CONFIRMED,
    referrer=None,
    commission_percent=None,
    emehmon_required=True,
) -> Reservation:
    assert_room_available(room, check_in, check_out)
    if guest is not None and getattr(guest, "is_blacklisted", False):
        reason = getattr(guest, "blacklist_reason", "") or "blacklisted"
        raise ValidationError(_("Mehmon qora ro‘yxatda: %(r)s") % {"r": reason})
    if room and room.room_type_id != room_type.id:
        raise AvailabilityError(_("Xona turi mos kelmaydi."))
    if referrer and commission_percent is None:
        commission_percent = referrer.default_commission_percent
    if not referrer:
        commission_percent = None
    reservation = Reservation(
        tenant=tenant,
        hotel=property_obj,
        guest=guest,
        company=company,
        group=group,
        referrer=referrer,
        commission_percent=commission_percent,
        room_type=room_type,
        room=room,
        rate_plan=rate_plan,
        nightly_rate=nightly_rate,
        emehmon_required=bool(emehmon_required),
        check_in=check_in,
        check_out=check_out,
        adults=adults,
        children=children,
        source=source,
        notes=notes,
        status=status,
        created_by=user,
        code=generate_reservation_code(tenant, property_obj, check_in),
        currency=(
            currency
            or getattr(rate_plan, "currency", None)
            or getattr(room_type, "currency", None)
            or getattr(tenant, "currency", None)
            or "UZS"
        ),
    )
    reservation.total_amount = recompute_total(reservation)
    reservation.full_clean()
    reservation.save()
    return reservation


def generate_group_code(tenant, on_date: date | None = None) -> str:
    day = on_date or timezone.localdate()
    prefix = f"GRP-{day.year}-"
    last = (
        ReservationGroup.objects.filter(tenant=tenant, code__startswith=prefix)
        .order_by("-code")
        .values_list("code", flat=True)
        .first()
    )
    if last:
        try:
            n = int(last.split("-")[-1]) + 1
        except ValueError:
            n = 1
    else:
        n = 1
    return f"{prefix}{n:04d}"


@transaction.atomic
def create_group_booking(
    *,
    tenant,
    user,
    property_obj,
    name,
    check_in,
    check_out,
    rooms_data: list,
    company=None,
    notes="",
):
    """rooms_data items: guest, room_type, room?, rate_plan?, adults?, children?"""
    if check_out <= check_in:
        raise ValidationError(_("Chiqish sanasi kirishdan keyin bo‘lishi kerak."))
    if not rooms_data:
        raise ValidationError(_("Guruhga kamida bitta xona qo‘shing."))

    group = ReservationGroup.objects.create(
        tenant=tenant,
        code=generate_group_code(tenant, check_in),
        name=name,
        hotel=property_obj,
        company=company,
        check_in=check_in,
        check_out=check_out,
        notes=notes or "",
        created_by=user,
    )
    created = []
    for item in rooms_data:
        created.append(
            create_reservation(
                tenant=tenant,
                user=user,
                property_obj=property_obj,
                guest=item["guest"],
                company=company,
                group=group,
                room_type=item["room_type"],
                room=item.get("room"),
                rate_plan=item.get("rate_plan"),
                nightly_rate=item.get("nightly_rate"),
                currency=item.get("currency"),
                check_in=check_in,
                check_out=check_out,
                adults=item.get("adults") or 1,
                children=item.get("children") or 0,
                source=Reservation.Source.OTHER,
                notes=item.get("notes") or "",
            )
        )
    return group, created


def _aware_local(day: date, t) -> datetime:
    naive = datetime.combine(day, t)
    if timezone.is_naive(naive):
        return timezone.make_aware(naive, timezone.get_current_timezone())
    return naive


def _post_timing_fee(folio, user, *, amount, description, marker: str, legacy_markers=()):
    from django.db.models import Q

    from folio.models import FolioCharge
    from folio.services import add_charge

    if amount is None or amount <= 0:
        return None
    prefixes = (marker, *legacy_markers)
    already = Q()
    for prefix in prefixes:
        already |= Q(description__startswith=prefix)
    if folio.charges.filter(already, is_void=False).exists():
        return None
    # Early/late fee sozlamalari tenant bazaviy valyutasida (so‘m/$/€)
    return add_charge(
        folio,
        user,
        charge_type=FolioCharge.ChargeType.OTHER,
        description=f"{marker}: {description}",
        unit_price=amount,
        quantity=Decimal("1"),
        currency=folio.tenant.currency or "UZS",
    )


@transaction.atomic
def check_in_reservation(
    reservation: Reservation,
    user,
    *,
    allow_dirty: bool = False,
    allow_no_docs: bool = False,
) -> Stay:
    if reservation.status not in {Reservation.Status.CONFIRMED, Reservation.Status.INQUIRY}:
        raise ValidationError(_("Faqat tasdiqlangan/so‘rov bronlar joylashishi mumkin."))
    if reservation.guest_id and reservation.guest.is_blacklisted:
        reason_txt = reservation.guest.blacklist_reason or "blacklisted"
        raise ValidationError(_("Mehmon qora ro‘yxatda: %(r)s") % {"r": reason_txt})
    settings = _property_settings(reservation)
    if (
        settings
        and settings.require_id_on_checkin
        and reservation.guest_id
        and not guest_has_id_document(reservation.guest)
        and not allow_no_docs
    ):
        raise MissingGuestDocsError(
            _("Mehmonda pasport/ID yo‘q; hujjat qo‘shing yoki hujjat ruxsatini bering.")
        )
    if reservation.room is None:
        raise ValidationError(_("Joylashdan oldin xona biriktiring."))
    assert_room_available(
        reservation.room,
        reservation.check_in,
        reservation.check_out,
        exclude_reservation_id=reservation.pk,
    )
    assert_room_physically_free(
        reservation.room, exclude_reservation_id=reservation.pk
    )
    room = reservation.room
    if room.status in ROOM_NOT_READY_FOR_CHECKIN and not allow_dirty:
        raise DirtyRoomError(
            _("Xona %(n)s holati: %(s)s; avval tozalang yoki kir xona ruxsatini bering.")
            % {"n": room.number, "s": room.get_status_display()}
        )
    now = timezone.now()
    reservation.status = Reservation.Status.CHECKED_IN
    reservation.save(update_fields=["status", "updated_at"])
    stay, created = Stay.objects.get_or_create(
        reservation=reservation,
        defaults={
            "tenant": reservation.tenant,
            "actual_check_in": now,
            "checked_in_by": user,
        },
    )
    if not created:
        stay.actual_check_in = now
        stay.checked_in_by = user
        stay.save(update_fields=["actual_check_in", "checked_in_by", "updated_at"])

    from folio.services import ensure_folio_for_reservation, ensure_stay_nights_posted

    folio = ensure_folio_for_reservation(reservation)
    if folio.stay_id is None:
        folio.stay = stay
        folio.save(update_fields=["stay", "updated_at"])
    # Joylashganda kecha to‘lovlarini yozamiz — depozit/to‘lov qarzga tushadi.
    ensure_stay_nights_posted(reservation, user)

    if settings and settings.early_checkin_fee > 0:
        standard = _aware_local(reservation.check_in, settings.checkin_time)
        if now < standard:
            _post_timing_fee(
                folio,
                user,
                amount=settings.early_checkin_fee,
                description=_("%(time)s dan oldin") % {"time": settings.checkin_time.strftime("%H:%M")},
                marker=_("Erta joylash to‘lovi"),
                legacy_markers=("Early check-in fee",),
            )
    log_activity(
        tenant=reservation.tenant,
        user=user,
        action="guest_check_in",
        model="Reservation",
        object_id=reservation.pk,
        payload={"code": reservation.code, "room": reservation.room.number if reservation.room_id else ""},
    )
    return stay


def check_out_reservation(reservation: Reservation, user) -> Stay:
    if reservation.status != Reservation.Status.CHECKED_IN:
        raise ValidationError(_("Faqat joylashgan bronlar chiqishi mumkin."))

    from folio.services import (
        ensure_folio_for_reservation,
        ensure_stay_nights_posted,
        reopen_folio,
    )
    from housekeeping.models import HousekeepingTask

    now = timezone.now()

    # Post room nights + late fee first and commit so unpaid checkout still
    # leaves charges on the folio for the guest to settle.
    with transaction.atomic():
        folio = ensure_folio_for_reservation(reservation)
        if not folio.is_open:
            reopen_folio(folio)
        settings = _property_settings(reservation)
        if settings and settings.late_checkout_fee > 0:
            standard = _aware_local(reservation.check_out, settings.checkout_time)
            if now > standard:
                _post_timing_fee(
                    folio,
                    user,
                    amount=settings.late_checkout_fee,
                    description=_("%(time)s dan keyin") % {"time": settings.checkout_time.strftime("%H:%M")},
                    marker=_("Kechikkan chiqish to‘lovi"),
                    legacy_markers=("Late check-out fee",),
                )
        ensure_stay_nights_posted(reservation, user)

    folio = ensure_folio_for_reservation(reservation)
    if folio.balance > 0:
        raise ValidationError(
            _("To‘lanmagan qoldiq %(b)s — chiqish mumkin emas.") % {"b": folio.balance}
        )

    with transaction.atomic():
        stay = reservation.stay
        stay.actual_check_out = now
        stay.checked_out_by = user
        stay.save(update_fields=["actual_check_out", "checked_out_by", "updated_at"])
        reservation.status = Reservation.Status.CHECKED_OUT
        reservation.save(update_fields=["status", "updated_at"])
        if reservation.room_id:
            reservation.room.status = Room.Status.DIRTY
            reservation.room.save(update_fields=["status", "updated_at"])
            HousekeepingTask.objects.create(
                tenant=reservation.tenant,
                room=reservation.room,
                title=_("Chiqishdan keyin tozalash"),
            )
        # Chiqishdan keyin hisobni yopamiz (qoldiq 0 yoki ortiqcha avans bo‘lsa ham)
        if folio.is_open and folio.balance == 0:
            folio.is_open = False
            folio.closed_at = now
            folio.save(update_fields=["is_open", "closed_at", "updated_at"])
    log_activity(
        tenant=reservation.tenant,
        user=user,
        action="guest_check_out",
        model="Reservation",
        object_id=reservation.pk,
        payload={"code": reservation.code, "room": reservation.room.number if reservation.room_id else ""},
    )
    return stay


@transaction.atomic
def apply_amendment(reservation: Reservation, user, data: dict) -> Reservation:
    if reservation.status in {
        Reservation.Status.CANCELLED,
        Reservation.Status.NO_SHOW,
        Reservation.Status.CHECKED_OUT,
    }:
        raise ValidationError(_("Yopilgan bronni o‘zgartirib bo‘lmaydi."))

    new_check_in = data["check_in"]
    new_check_out = data["check_out"]
    new_room = data.get("room")
    new_rate = data.get("rate_plan")
    new_nightly = data.get("nightly_rate")
    new_adults = data["adults"]
    new_children = data["children"]
    reason = data.get("reason") or ""

    if new_check_out <= new_check_in:
        raise ValidationError(_("Chiqish sanasi kirishdan keyin bo‘lishi kerak."))

    assert_room_available(
        new_room or reservation.room,
        new_check_in,
        new_check_out,
        exclude_reservation_id=reservation.pk,
    )

    pairs = [
        ("check_in", reservation.check_in, new_check_in),
        ("check_out", reservation.check_out, new_check_out),
        ("room", reservation.room_id, new_room.pk if new_room else None),
        ("rate_plan", reservation.rate_plan_id, new_rate.pk if new_rate else None),
        ("nightly_rate", reservation.nightly_rate, new_nightly),
        ("currency", reservation.currency, data.get("currency")),
        ("adults", reservation.adults, new_adults),
        ("children", reservation.children, new_children),
    ]
    for field, old, new in pairs:
        if old != new:
            log_change(reservation, user, field, old, new, reason=reason)

    reservation.check_in = new_check_in
    reservation.check_out = new_check_out
    reservation.room = new_room
    if "nightly_rate" in data:
        reservation.nightly_rate = new_nightly
        # Qo‘lda narx berilsa — eski tarif bog‘lanishini olib tashlash
        if new_nightly is not None:
            reservation.rate_plan = None
        elif new_rate is not None:
            reservation.rate_plan = new_rate
    elif new_rate is not None:
        reservation.rate_plan = new_rate
    if data.get("currency"):
        reservation.currency = data["currency"]
    if new_room:
        old_type_id = reservation.room_type_id
        reservation.room_type = new_room.room_type
        if old_type_id != new_room.room_type_id:
            log_change(
                reservation,
                user,
                "room_type",
                old_type_id,
                new_room.room_type_id,
                reason=reason,
            )
            # Qo‘lda narx yo‘q va tarif eski turga bog‘liq — yangi tur BAR
            if (
                data.get("update_rate", True)
                and reservation.nightly_rate is None
                and (
                    reservation.rate_plan_id is None
                    or getattr(reservation.rate_plan, "room_type_id", None)
                    != new_room.room_type_id
                )
            ):
                auto_rate = (
                    RatePlan.objects.filter(
                        property=reservation.hotel,
                        room_type=new_room.room_type,
                        is_active=True,
                        is_default=True,
                    ).first()
                    or RatePlan.objects.filter(
                        property=reservation.hotel,
                        room_type=new_room.room_type,
                        is_active=True,
                    ).first()
                )
                if auto_rate and auto_rate.pk != reservation.rate_plan_id:
                    log_change(
                        reservation,
                        user,
                        "rate_plan",
                        reservation.rate_plan_id,
                        auto_rate.pk,
                        reason=reason or "room_type_swap",
                    )
                    reservation.rate_plan = auto_rate
    reservation.adults = new_adults
    reservation.children = new_children
    reservation.total_amount = recompute_total(reservation)
    reservation.full_clean()
    reservation.save()
    return reservation


@transaction.atomic
def _ensure_fee_folio(reservation: Reservation, user):
    """Open a folio for fee/deposit posting even before check-in."""
    from folio.services import ensure_folio_for_reservation

    return ensure_folio_for_reservation(reservation, allow_pre_checkin=True)


def _property_settings(reservation: Reservation):
    from properties.models import PropertySettings

    return PropertySettings.objects.filter(property=reservation.hotel).first()


@transaction.atomic
def cancel_reservation(reservation: Reservation, user, reason="") -> Reservation:
    if reservation.status in {
        Reservation.Status.CHECKED_OUT,
        Reservation.Status.CANCELLED,
    }:
        raise ValidationError(_("Bron allaqachon yopilgan."))
    old = reservation.status
    settings = _property_settings(reservation)
    fee_percent = settings.cancel_fee_percent if settings else Decimal("0")
    fee = (reservation.total_amount * fee_percent / Decimal("100")).quantize(Decimal("0.01"))

    reservation.status = Reservation.Status.CANCELLED
    reservation.save(update_fields=["status", "updated_at"])
    log_change(reservation, user, "status", old, reservation.status, reason=reason)

    if fee > 0:
        from folio.models import FolioCharge
        from folio.services import add_charge

        folio = _ensure_fee_folio(reservation, user)
        add_charge(
            folio,
            user,
            charge_type=FolioCharge.ChargeType.CANCEL,
            description=_("Bekor qilish to‘lovi (%(p)s%%)") % {"p": fee_percent},
            unit_price=fee,
            quantity=Decimal("1"),
            currency=getattr(reservation, "currency", None) or reservation.tenant.currency,
        )
    return reservation


@transaction.atomic
def confirm_inquiry(reservation: Reservation, user, reason="") -> Reservation:
    if reservation.status != Reservation.Status.INQUIRY:
        raise ValidationError(_("Faqat so‘rov bronlar tasdiqlanadi."))
    if reservation.guest_id and reservation.guest.is_blacklisted:
        reason_txt = reservation.guest.blacklist_reason or "blacklisted"
        raise ValidationError(_("Mehmon qora ro‘yxatda: %(r)s") % {"r": reason_txt})
    old = reservation.status
    reservation.status = Reservation.Status.CONFIRMED
    reservation.save(update_fields=["status", "updated_at"])
    log_change(reservation, user, "status", old, reservation.status, reason=reason or "Confirmed inquiry")
    return reservation


@transaction.atomic
def mark_no_show(reservation: Reservation, user, reason="") -> Reservation:
    """
    Kelmagan (no-show): jarima yozilmaydi.
    Foliodagi yashash/jarima yozuvlari bekor, olingan to‘lovlar qaytariladi.
    """
    if reservation.status != Reservation.Status.CONFIRMED:
        raise ValidationError(_("Faqat tasdiqlangan bronlar kelmagan deb belgilanadi."))
    old = reservation.status

    reservation.status = Reservation.Status.NO_SHOW
    reservation.save(update_fields=["status", "updated_at"])
    log_change(
        reservation,
        user,
        "status",
        old,
        reservation.status,
        reason=reason or _("Kelmagan — jarimasiz, to‘lov qaytariladi"),
    )
    _settle_no_show_folio(reservation, user)
    return reservation


def _settle_no_show_folio(reservation: Reservation, user) -> None:
    """Jarimasiz: stay charge’larni void + net to‘lovni refund (kun yopiq bo‘lsa ham)."""
    from django.core.exceptions import ValidationError as DjangoValidationError
    from django.utils import timezone as dj_tz

    from folio.models import Folio, FolioCharge, GuestPayment
    from folio.services import emehmon_charge_q, refund_overpayment

    folio = Folio.objects.filter(reservation=reservation, is_open=True).first()
    if folio is None:
        return

    reason = str(_("Kelmagan — jarimasiz, hisob tozalandi"))
    for charge in folio.charges.filter(is_void=False).exclude(emehmon_charge_q()):
        charge.is_void = True
        charge.void_reason = reason
        charge.voided_at = dj_tz.now()
        charge.voided_by = user
        charge.save(
            update_fields=[
                "is_void",
                "void_reason",
                "voided_at",
                "voided_by",
                "updated_at",
            ]
        )

    folio = Folio.objects.get(pk=folio.pk)
    if folio.credit_amount <= 0:
        return

    last_pay = (
        folio.payments.filter(is_void=False)
        .exclude(kind=GuestPayment.Kind.REFUND)
        .order_by("-id")
        .first()
    )
    method = last_pay.method if last_pay else GuestPayment.Method.CASH
    try:
        refund_overpayment(
            folio,
            user,
            method=method,
            note=_("Kelmagan — to‘lovni qaytarish"),
            currency=getattr(last_pay, "currency", None) if last_pay else None,
        )
    except DjangoValidationError:
        # Masalan kassa smenasi yo‘q — credit folio da qoladi, kassir qo‘lda qaytaradi
        pass


def clear_existing_no_show_penalties(*, tenant=None, user=None, dry_run: bool = True) -> dict:
    """
    Allaqachon «Kelmagan» bronlardagi jarima/yashash yozuvlarini tozalash.
    Yangi siyosat: jarima yo‘q, to‘lov qaytariladi.
    """
    from folio.models import FolioCharge

    qs = Reservation.objects.filter(status=Reservation.Status.NO_SHOW)
    if tenant is not None:
        qs = qs.filter(tenant=tenant)
    qs = qs.select_related("folio", "hotel").order_by("id")

    touched = []
    void_count = 0
    for res in qs:
        folio = getattr(res, "folio", None)
        if folio is None or not folio.is_open:
            continue
        penalties = list(
            FolioCharge.objects.filter(
                folio=folio,
                is_void=False,
                charge_type__in=[
                    FolioCharge.ChargeType.PENALTY,
                    FolioCharge.ChargeType.ROOM,
                    FolioCharge.ChargeType.CANCEL,
                ],
            )
        )
        # Also any non-emehmon stay charge with незаезд/kelmagan in description
        extra = list(
            FolioCharge.objects.filter(folio=folio, is_void=False).exclude(
                charge_type=FolioCharge.ChargeType.EMEHMON
            )
        )
        charges = {c.pk: c for c in penalties + extra}
        if not charges and folio.credit_amount <= 0:
            continue
        touched.append(res.code)
        if dry_run:
            void_count += len(charges)
            continue
        _settle_no_show_folio(res, user)
        void_count += len(charges)

    return {"reservations": touched, "void_candidates": void_count, "dry_run": dry_run}


@transaction.atomic
def transfer_room(
    reservation: Reservation,
    user,
    new_room,
    reason="",
    *,
    update_rate: bool = True,
) -> Reservation:
    """
    Joylashgan mehmonni boshqa xonaga o‘tkazish.
    Double↔Twin va boshqa turlar ham mumkin — room_type yangi xonadan olinadi.
    """
    if reservation.status != Reservation.Status.CHECKED_IN:
        raise ValidationError(_("Faqat joylashgan mehmonlar xona o‘tkazishi mumkin."))
    if new_room is None:
        raise ValidationError(_("Yangi xona kerak."))
    if new_room.property_id != reservation.hotel_id:
        raise ValidationError(_("Xona boshqa filialga tegishli."))
    assert_room_available(
        new_room,
        reservation.check_in,
        reservation.check_out,
        exclude_reservation_id=reservation.pk,
    )
    old_room = reservation.room
    old_type_id = reservation.room_type_id
    old_rate_id = reservation.rate_plan_id

    log_change(
        reservation,
        user,
        "room",
        old_room.pk if old_room else None,
        new_room.pk,
        reason=reason or "transfer",
    )
    reservation.room = new_room
    reservation.room_type = new_room.room_type
    if old_type_id != new_room.room_type_id:
        log_change(
            reservation,
            user,
            "room_type",
            old_type_id,
            new_room.room_type_id,
            reason=reason or "transfer",
        )

    # Qo‘lda kecha narxi bor — tarifga qaytarmaymiz
    if (
        update_rate
        and reservation.nightly_rate is None
        and (
            reservation.rate_plan_id is None
            or reservation.rate_plan.room_type_id != new_room.room_type_id
        )
    ):
        new_rate = (
            RatePlan.objects.filter(
                property=reservation.hotel,
                room_type=new_room.room_type,
                is_active=True,
                is_default=True,
            ).first()
            or RatePlan.objects.filter(
                property=reservation.hotel,
                room_type=new_room.room_type,
                is_active=True,
            ).first()
        )
        if new_rate and new_rate.pk != old_rate_id:
            log_change(
                reservation,
                user,
                "rate_plan",
                old_rate_id,
                new_rate.pk,
                reason=reason or "transfer",
            )
            reservation.rate_plan = new_rate

    reservation.total_amount = recompute_total(reservation)
    reservation.save()
    if old_room:
        old_room.status = Room.Status.DIRTY
        old_room.save(update_fields=["status", "updated_at"])
        from housekeeping.models import HousekeepingTask

        HousekeepingTask.objects.create(
            tenant=reservation.tenant,
            room=old_room,
            title=_("Xona almashtirishdan keyin tozalash"),
        )
    return reservation
