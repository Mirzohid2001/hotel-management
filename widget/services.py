"""Veb-saytdan bron — bandlik va yaratish."""

from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from bookings.models import Reservation
from bookings.services import (
    AvailabilityError,
    assert_room_available,
    create_reservation,
)
from core.models import log_activity
from guests.models import Guest
from properties.models import Property, RatePlan, Room, RoomType
from properties.services import quote_stay

from .models import WidgetConfig


class WidgetError(Exception):
    def __init__(self, message, code="error"):
        self.message = message
        self.code = code
        super().__init__(message)


def resolve_widget(tenant_slug: str, branch_code: str | None = None) -> tuple[WidgetConfig, "tenants.Tenant"]:
    from tenants.models import Tenant

    tenant = Tenant.objects.filter(slug=tenant_slug, is_active=True).first()
    if tenant is None:
        raise WidgetError(_("Mehmonxona topilmadi."), "not_found")
    if not branch_code:
        config = (
            WidgetConfig.objects.filter(tenant=tenant, is_enabled=True)
            .select_related("hotel")
            .order_by("hotel__name")
            .first()
        )
        if config is None:
            raise WidgetError(_("Onlayn bron vaqtincha o‘chirilgan."), "disabled")
    else:
        prop = Property.objects.filter(
            tenant=tenant, branch_code__iexact=branch_code, is_active=True
        ).first()
        if prop is None:
            raise WidgetError(_("Filial topilmadi."), "not_found")
        config = getattr(prop, "widget_config", None)
        if config is None or not config.is_enabled:
            raise WidgetError(_("Onlayn bron vaqtincha o‘chirilgan."), "disabled")
    if not tenant.has_feature("online_booking"):
        raise WidgetError(_("Tarifda onlayn bron yo‘q."), "plan")
    sub = tenant.get_active_subscription()
    if sub is None or not sub.is_currently_valid():
        raise WidgetError(_("Obuna faol emas."), "subscription")
    return config, tenant


def resolve_property(config: WidgetConfig, tenant) -> Property:
    prop = config.hotel
    if prop.tenant_id != tenant.id or not prop.is_active:
        raise WidgetError(_("Filial sozlanmagan."), "no_property")
    return prop


def _default_rate(tenant, prop, room_type) -> RatePlan | None:
    rate = RatePlan.objects.filter(
        tenant=tenant,
        property=prop,
        room_type=room_type,
        is_default=True,
        is_active=True,
    ).first()
    if rate:
        return rate
    return RatePlan.objects.filter(
        tenant=tenant,
        property=prop,
        room_type=room_type,
        is_active=True,
    ).first()


def available_rooms_for_type(
    tenant,
    prop,
    room_type,
    check_in: date,
    check_out: date,
) -> list[Room]:
    rooms = Room.objects.filter(
        tenant=tenant,
        property=prop,
        room_type=room_type,
        is_active=True,
    ).exclude(status=Room.Status.OUT_OF_ORDER)
    free = []
    for room in rooms:
        try:
            assert_room_available(room, check_in, check_out)
            free.append(room)
        except AvailabilityError:
            continue
    return free


def room_type_availability(
    tenant,
    prop,
    *,
    check_in: date,
    check_out: date,
    adults: int = 1,
) -> list[dict]:
    if check_out <= check_in:
        raise WidgetError(_("Chiqish sanasi noto‘g‘ri."), "dates")
    nights = (check_out - check_in).days
    rows = []
    room_types = RoomType.objects.filter(
        tenant=tenant, property=prop, is_active=True
    ).order_by("name")
    for rt in room_types:
        if rt.capacity_adults < adults:
            continue
        free_rooms = available_rooms_for_type(tenant, prop, rt, check_in, check_out)
        rate = _default_rate(tenant, prop, rt)
        if rate:
            price = quote_stay(rate, check_in, check_out, adults=adults)
        else:
            price = (rt.base_price or 0) * nights
        rows.append(
            {
                "id": rt.pk,
                "name": rt.name,
                "description": rt.description,
                "capacity_adults": rt.capacity_adults,
                "capacity_children": rt.capacity_children,
                "available": len(free_rooms) > 0,
                "available_count": len(free_rooms),
                "nights": nights,
                "price_total": str(price),
                "currency": tenant.currency,
            }
        )
    return rows


def get_or_create_web_guest(
    tenant,
    *,
    first_name: str,
    last_name: str,
    phone: str,
    email: str,
) -> Guest:
    phone = (phone or "").strip()
    email = (email or "").strip().lower()
    if not first_name.strip():
        raise WidgetError(_("Ism majburiy."), "validation")
    if not phone and not email:
        raise WidgetError(_("Telefon yoki email kiriting."), "validation")
    guest = None
    if phone:
        guest = Guest.objects.filter(tenant=tenant, phone=phone).first()
    if guest is None and email:
        guest = Guest.objects.filter(tenant=tenant, email=email).first()
    if guest is None:
        guest = Guest.objects.create(
            tenant=tenant,
            first_name=first_name.strip(),
            last_name=(last_name or "").strip(),
            phone=phone,
            email=email,
        )
    else:
        updated = []
        if not guest.phone and phone:
            guest.phone = phone
            updated.append("phone")
        if not guest.email and email:
            guest.email = email
            updated.append("email")
        if updated:
            guest.save(update_fields=updated)
    if guest.is_blacklisted:
        raise WidgetError(_("Bron qabul qilinmaydi."), "blacklist")
    return guest


@transaction.atomic
def create_web_booking(
    config: WidgetConfig,
    tenant,
    *,
    room_type_id: int,
    check_in: date,
    check_out: date,
    first_name: str,
    last_name: str,
    phone: str,
    email: str,
    adults: int = 2,
    children: int = 0,
    notes: str = "",
) -> Reservation:
    prop = resolve_property(config, tenant)
    try:
        room_type = RoomType.objects.get(
            pk=room_type_id, tenant=tenant, property=prop, is_active=True
        )
    except RoomType.DoesNotExist as exc:
        raise WidgetError(_("Xona turi topilmadi."), "room_type") from exc

    free_rooms = available_rooms_for_type(tenant, prop, room_type, check_in, check_out)
    if not free_rooms:
        raise WidgetError(
            _("Tanlangan sanalarda bu xona turi band (zaynit)."),
            "unavailable",
        )

    room = free_rooms[0] if config.auto_assign_room else None

    guest = get_or_create_web_guest(
        tenant,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        email=email,
    )
    rate = _default_rate(tenant, prop, room_type)
    status = (
        Reservation.Status.CONFIRMED
        if config.auto_confirm
        else Reservation.Status.INQUIRY
    )
    note_parts = [notes.strip()] if notes.strip() else []
    note_parts.append(_("Onlayn bron (veb-sayt)"))
    try:
        reservation = create_reservation(
            tenant=tenant,
            user=None,
            property_obj=prop,
            guest=guest,
            room_type=room_type,
            room=room,
            rate_plan=rate,
            check_in=check_in,
            check_out=check_out,
            adults=adults,
            children=children,
            source=Reservation.Source.WEBSITE,
            notes=" · ".join(note_parts),
            status=status,
        )
    except (AvailabilityError, ValidationError) as exc:
        msgs = exc.messages if hasattr(exc, "messages") else [str(exc)]
        raise WidgetError("; ".join(msgs), "unavailable") from exc

    log_activity(
        tenant=tenant,
        user=None,
        action="web_booking",
        model="Reservation",
        object_id=reservation.pk,
        payload={
            "code": reservation.code,
            "guest": guest.full_name,
            "status": reservation.status,
            "property": prop.name,
            "source": "website",
        },
    )
    return reservation
