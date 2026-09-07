"""Xona bandligi — walk-in va bron formalari uchun."""

from datetime import date

from properties.models import Room

from .services import AvailabilityError, ROOM_NOT_READY_FOR_CHECKIN, assert_room_available


def room_availability_split(tenant, hotel, check_in: date, check_out: date):
    """(bo'sh_xonalar, band_xonalar) — sanalar kesishmasi bo'yicha."""
    cards = walk_in_room_cards(tenant, hotel, check_in, check_out)
    available = [c["room"] for c in cards if c["state"] in {"free", "dirty"}]
    occupied = [c["room"] for c in cards if c["state"] == "occupied"]
    return available, occupied


def walk_in_room_cards(tenant, hotel, check_in: date, check_out: date) -> list[dict]:
    """Har bir xona: free | dirty | occupied."""
    qs = Room.objects.filter(tenant=tenant, is_active=True, room_type__is_active=True).exclude(
        status=Room.Status.OUT_OF_ORDER
    )
    if hotel is not None:
        qs = qs.filter(property=hotel)
    cards = []
    for room in qs.select_related("room_type").order_by("number"):
        try:
            assert_room_available(room, check_in, check_out)
            state = "dirty" if room.status in ROOM_NOT_READY_FOR_CHECKIN else "free"
        except AvailabilityError:
            state = "occupied"
        cards.append({"room": room, "state": state})
    return cards
