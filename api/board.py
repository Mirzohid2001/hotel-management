"""Board data for mobile — mirrors bookings.views.board queries (web unchanged)."""

from datetime import date, timedelta

from django.utils import timezone

from bookings.models import Reservation
from folio.models import Folio
from properties.models import Room


def build_board(*, tenant, hotel=None, day: date | None = None) -> dict:
    day = day or timezone.localdate()
    rooms = Room.objects.filter(tenant=tenant, is_active=True).select_related(
        "room_type", "property"
    )
    if hotel is not None:
        rooms = rooms.filter(property=hotel)

    active = (
        Reservation.objects.filter(tenant=tenant)
        .overlapping(day, day + timedelta(days=1))
        .select_related("guest", "room")
    )
    if hotel is not None:
        active = active.filter(hotel=hotel)

    still_in = (
        Reservation.objects.filter(tenant=tenant)
        .checked_in_on_room()
        .select_related("guest", "room")
    )
    if hotel is not None:
        still_in = still_in.filter(hotel=hotel)

    by_room = {r.room_id: r for r in active if r.room_id}
    for r in still_in:
        if r.room_id:
            by_room[r.room_id] = r

    folio_map = {}
    if by_room:
        for folio in Folio.objects.filter(
            tenant=tenant,
            reservation_id__in=[r.pk for r in by_room.values()],
        ):
            folio_map[folio.reservation_id] = folio

    tiles = []
    stats = {"total": 0, "vacant": 0, "occupied": 0, "dirty": 0, "ooo": 0}
    for room in rooms:
        reservation = by_room.get(room.pk)
        folio = folio_map.get(reservation.pk) if reservation else None
        if room.status == Room.Status.OUT_OF_ORDER:
            state = "ooo"
            stats["ooo"] += 1
        elif reservation:
            state = "occupied"
            stats["occupied"] += 1
        elif room.status in (Room.Status.DIRTY, Room.Status.CLEANING):
            state = "dirty"
            stats["dirty"] += 1
        else:
            state = "vacant"
            stats["vacant"] += 1
        stats["total"] += 1

        tile = {
            "room": {
                "id": room.pk,
                "number": room.number,
                "status": room.status,
                "room_type": room.room_type.name if room.room_type_id else "",
                "hotel_id": room.property_id,
            },
            "state": state,
            "reservation": None,
            "folio": None,
        }
        if reservation:
            tile["reservation"] = {
                "id": reservation.pk,
                "code": reservation.code,
                "status": reservation.status,
                "check_in": reservation.check_in.isoformat(),
                "check_out": reservation.check_out.isoformat(),
                "guest": {
                    "id": reservation.guest_id,
                    "name": str(reservation.guest) if reservation.guest_id else "",
                },
                "adults": reservation.adults,
                "children": reservation.children,
            }
        if folio:
            tile["folio"] = {
                "id": folio.pk,
                "balance": str(folio.balance),
                "is_open": folio.is_open,
            }
        tiles.append(tile)

    return {
        "day": day.isoformat(),
        "stats": stats,
        "tiles": tiles,
        "hotel_id": hotel.pk if hotel else None,
    }
