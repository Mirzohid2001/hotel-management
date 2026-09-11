from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from bookings.models import Reservation
from bookings.services import mark_no_show
from folio.models import Folio, FolioCharge
from folio.services import (
    add_charge,
    ensure_folio_for_reservation,
    folio_has_legacy_prepaid_room,
    folio_has_night_for_day,
    night_amount_for,
    night_charge_description,
)
from properties.models import Property, Room

from core.models import log_activity

from .models import NightAuditRun
from .services import adr_revpar, revenue_on


def _reservation_qs(tenant, hotel=None):
    qs = Reservation.objects.filter(tenant=tenant)
    if hotel is not None:
        qs = qs.filter(hotel=hotel)
    return qs


def _folio_qs(tenant, hotel=None):
    qs = Folio.objects.filter(tenant=tenant)
    if hotel is not None:
        qs = qs.filter(reservation__hotel=hotel)
    return qs


def _room_qs(tenant, hotel=None):
    qs = Room.objects.filter(tenant=tenant, is_active=True)
    if hotel is not None:
        qs = qs.filter(property=hotel)
    return qs


def build_cod_checklist(tenant, day: date, *, hotel: Property | None = None) -> dict:
    """Close-of-day checklist snapshot (does not mutate data)."""
    overdue = []
    folios = (
        _folio_qs(tenant, hotel)
        .filter(is_open=True)
        .select_related("reservation", "reservation__guest", "reservation__room")
        .order_by("reservation__code")
    )
    for folio in folios:
        if folio.balance <= 0:
            continue
        res = folio.reservation
        is_past_departure = (
            res.status == Reservation.Status.CHECKED_IN and res.check_out <= day
        )
        is_closed_owing = res.status in {
            Reservation.Status.CHECKED_OUT,
            Reservation.Status.CANCELLED,
            Reservation.Status.NO_SHOW,
        }
        if is_past_departure or is_closed_owing:
            overdue.append(
                {
                    "code": res.code,
                    "guest": res.guest.full_name,
                    "balance": str(folio.balance),
                    "status": res.status,
                    "pk": res.pk,
                }
            )

    missed_arrivals = list(
        _reservation_qs(tenant, hotel)
        .filter(status=Reservation.Status.CONFIRMED, check_in__lte=day)
        .select_related("guest", "room")
        .order_by("check_in", "code")
        .values("pk", "code", "guest__first_name", "guest__last_name", "room__number")[:40]
    )

    still_in_house_past_out = list(
        _reservation_qs(tenant, hotel)
        .filter(status=Reservation.Status.CHECKED_IN, check_out__lte=day)
        .select_related("guest", "room")
        .order_by("check_out", "code")
        .values("pk", "code", "guest__first_name", "guest__last_name", "room__number", "check_out")[:40]
    )

    dirty_room_list = list(
        _room_qs(tenant, hotel)
        .filter(status=Room.Status.DIRTY)
        .select_related("property")
        .order_by("number")
        .values("pk", "number", "property__name")[:30]
    )

    dirty_rooms = _room_qs(tenant, hotel).filter(status=Room.Status.DIRTY).count()

    return {
        "missed_arrivals": missed_arrivals,
        "overdue_folios": overdue,
        "still_in_house_past_out": still_in_house_past_out,
        "still_in_house_past_out_count": len(still_in_house_past_out),
        "dirty_rooms": dirty_rooms,
        "dirty_room_list": dirty_room_list,
    }


def audit_blockers(tenant, day: date, *, hotel: Property | None = None) -> list[dict]:
    checklist = build_cod_checklist(tenant, day, hotel=hotel)
    blockers = []
    if checklist["overdue_folios"]:
        blockers.append(
            {
                "key": "overdue_folios",
                "count": len(checklist["overdue_folios"]),
                "label": _("Qarzdor hisoblar"),
            }
        )
    if checklist["still_in_house_past_out_count"]:
        blockers.append(
            {
                "key": "still_in_house",
                "count": checklist["still_in_house_past_out_count"],
                "label": _("Muddat o‘tib hali ichkarida"),
            }
        )
    return blockers


def assert_audit_ready(tenant, day: date, *, hotel: Property | None = None) -> None:
    blockers = audit_blockers(tenant, day, hotel=hotel)
    if not blockers:
        return
    parts = [f"{b['label']} ({b['count']})" for b in blockers]
    raise ValidationError(
        _("Kun yopish bloklangan — avval hal qiling: %(items)s") % {"items": "; ".join(parts)}
    )


@transaction.atomic
def run_night_audit(
    tenant,
    user,
    audit_date: date | None = None,
    *,
    hotel: Property,
) -> NightAuditRun:
    day = audit_date or timezone.localdate()
    if NightAuditRun.objects.filter(tenant=tenant, hotel=hotel, audit_date=day).exists():
        raise ValidationError(
            _("%(hotel)s — %(d)s kuni allaqachon yopilgan.")
            % {"d": day, "hotel": hotel.name}
        )
    assert_audit_ready(tenant, day, hotel=hotel)

    no_shows = 0
    missed = list(
        _reservation_qs(tenant, hotel)
        .filter(status=Reservation.Status.CONFIRMED, check_in__lte=day)
        .select_related("hotel")
    )
    for reservation in missed:
        mark_no_show(
            reservation,
            user,
            reason=f"Night audit {day.isoformat()} auto no-show",
        )
        no_shows += 1

    in_house = (
        _reservation_qs(tenant, hotel)
        .filter(
            status=Reservation.Status.CHECKED_IN,
            check_in__lte=day,
            check_out__gt=day,
        )
        .select_related("rate_plan", "room_type")
    )

    posted = 0
    for reservation in in_house:
        folio = ensure_folio_for_reservation(reservation)
        if folio_has_legacy_prepaid_room(folio):
            continue
        if folio_has_night_for_day(folio, day):
            continue
        add_charge(
            folio,
            user,
            charge_type=FolioCharge.ChargeType.ROOM,
            description=night_charge_description(day),
            unit_price=night_amount_for(reservation, day),
            quantity=Decimal("1"),
            currency=getattr(reservation, "currency", None) or tenant.currency,
        )
        posted += 1

    checklist = build_cod_checklist(tenant, day, hotel=hotel)
    open_folios = _folio_qs(tenant, hotel).filter(is_open=True).count()
    stats = adr_revpar(tenant, day, hotel=hotel)
    snapshot = {k: str(v) if isinstance(v, Decimal) else v for k, v in stats.items()}
    snapshot["cod"] = checklist
    snapshot["no_shows_marked"] = no_shows
    snapshot["hotel"] = hotel.name
    snapshot["base_currency"] = tenant.currency or "UZS"

    run = NightAuditRun.objects.create(
        tenant=tenant,
        hotel=hotel,
        audit_date=day,
        posted_room_charges=posted,
        open_folios=open_folios,
        no_shows_marked=no_shows,
        overdue_folios=len(checklist["overdue_folios"]),
        dirty_rooms=checklist["dirty_rooms"],
        occupancy_percent=stats["occupancy_percent"],
        revenue=revenue_on(tenant, day, hotel=hotel),
        snapshot=snapshot,
        run_by=user,
    )
    log_activity(
        tenant=tenant,
        user=user,
        action="night_audit_run",
        model="NightAuditRun",
        object_id=run.pk,
        payload={
            "audit_date": str(day),
            "hotel": hotel.name,
            "posted_room_charges": posted,
            "no_shows": no_shows,
        },
    )
    return run
