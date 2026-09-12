"""Xona bandligi — walk-in va bron formalari uchun."""

from datetime import date

from properties.models import Room

from .models import Reservation
from .services import AvailabilityError, ROOM_NOT_READY_FOR_CHECKIN, assert_room_available


def room_availability_split(tenant, hotel, check_in: date, check_out: date):
    """(bo'sh_xonalar, band_xonalar) — sanalar kesishmasi bo'yicha."""
    cards = walk_in_room_cards(tenant, hotel, check_in, check_out)
    available = [c["room"] for c in cards if c["state"] in {"free", "dirty"}]
    occupied = [c["room"] for c in cards if c["state"] == "occupied"]
    return available, occupied


def walk_in_room_cards(tenant, hotel, check_in: date, check_out: date) -> list[dict]:
    """Har bir xona: free | dirty | occupied.

    Checkout day is free in date math, but a guest still marked checked_in
    keeps the room Band until Chiqish — then same-day walk-in is allowed.
    """
    qs = Room.objects.filter(tenant=tenant, is_active=True, room_type__is_active=True).exclude(
        status=Room.Status.OUT_OF_ORDER
    )
    if hotel is not None:
        qs = qs.filter(property=hotel)
    in_house_ids = set(
        Reservation.objects.filter(tenant=tenant)
        .checked_in_on_room()
        .values_list("room_id", flat=True)
    )
    cards = []
    for room in qs.select_related("room_type").order_by("number"):
        try:
            assert_room_available(room, check_in, check_out)
            if room.pk in in_house_ids:
                # Still physically occupied (incl. departure morning before Chiqish).
                state = "occupied"
            else:
                state = "dirty" if room.status in ROOM_NOT_READY_FOR_CHECKIN else "free"
        except AvailabilityError:
            state = "occupied"
        cards.append({"room": room, "state": state})
    return cards
