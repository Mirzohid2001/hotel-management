"""Xona × kun shaxmatka (timeline) — doska va taqvim uchun."""

from datetime import date, timedelta
from decimal import Decimal

from folio.models import Folio
from properties.models import Room

from .models import Reservation


def build_room_timeline(tenant, hotel, start: date, *, days_count: int = 14) -> dict:
    days = [start + timedelta(days=i) for i in range(days_count)]
    end = days[-1] + timedelta(days=1)
    rooms = Room.objects.filter(tenant=tenant, is_active=True).select_related(
        "room_type", "property"
    )
    if hotel is not None:
        rooms = rooms.filter(property=hotel)

    reservations = (
        Reservation.objects.filter(tenant=tenant)
        .overlapping(start, end)
        .exclude(
            status__in=[
                Reservation.Status.CANCELLED,
                Reservation.Status.NO_SHOW,
            ]
        )
        .select_related("guest", "room")
    )
    if hotel is not None:
        reservations = reservations.filter(hotel=hotel)

    grid = {room.pk: {d: None for d in days} for room in rooms}
    res_by_id = {}
    for res in reservations:
        res_by_id[res.pk] = res
        if not res.room_id or res.room_id not in grid:
            continue
        for d in days:
            if res.check_in <= d < res.check_out:
                grid[res.room_id][d] = res

    folio_map = {}
    if res_by_id:
        for folio in Folio.objects.filter(
            tenant=tenant, reservation_id__in=list(res_by_id.keys())
        ):
            folio_map[folio.reservation_id] = folio

    def segments_for(room):
        day_map = grid[room.pk]
        segs = []
        i = 0
        while i < len(days):
            d = days[i]
            res = day_map[d]
            if res is None:
                segs.append(
                    {
                        "kind": "empty",
                        "date": d,
                        "check_out": d + timedelta(days=1),
                        "colspan": 1,
                        "room": room,
                    }
                )
                i += 1
                continue
            j = i + 1
            while j < len(days) and day_map[days[j]] is res:
                j += 1
            segs.append(
                {
                    "kind": "stay",
                    "reservation": res,
                    "folio": folio_map.get(res.pk),
                    "colspan": j - i,
                    "status": res.status,
                    "is_vip": bool(res.guest_id and res.guest.is_vip),
                    "start_day": days[i],
                    "covers_today": False,
                }
            )
            i = j
        return segs

    rows = []
    stay_count = 0
    vip_count = 0
    for room in rooms:
        segments = segments_for(room)
        for seg in segments:
            if seg["kind"] == "stay":
                stay_count += 1
                if seg["is_vip"]:
                    vip_count += 1
        rows.append({"room": room, "segments": segments})

    return {
        "days": days,
        "rows": rows,
        "start": start,
        "end": days[-1],
        "days_count": days_count,
        "folio_map": folio_map,
        "stats": {
            "rooms": len(rows),
            "stays": stay_count,
            "vip": vip_count,
            "vacant_cells": sum(
                1
                for row in rows
                for seg in row["segments"]
                if seg["kind"] == "empty"
            ),
        },
    }


def mark_covers_today(timeline: dict, today: date) -> None:
    for row in timeline["rows"]:
        for seg in row["segments"]:
            if seg["kind"] != "stay":
                continue
            res = seg["reservation"]
            seg["covers_today"] = res.check_in <= today < res.check_out
            folio = seg.get("folio")
            if folio is not None:
                seg["balance"] = folio.balance
            else:
                seg["balance"] = Decimal("0")
