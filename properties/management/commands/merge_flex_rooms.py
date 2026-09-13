"""Merge duplicate Twin/Double room rows (101 + 101-1) into one physical room."""

from __future__ import annotations

import re
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from bookings.models import Reservation
from bookings.services import AvailabilityError, assert_room_available
from properties.models import Property, Room
from tenants.models import Tenant


SUFFIX_RE = re.compile(r"^(.+)-(\d+)$")


def base_number(number: str) -> str | None:
    m = SUFFIX_RE.match((number or "").strip())
    return m.group(1) if m else None


class Command(BaseCommand):
    help = (
        "101 va 101-1 kabi dublikat xonalarni birlashtiradi: "
        "asosiy xonaga Twin/Double sellable_types qo‘shadi, bronlarni ko‘chiradi "
        "(Reservation.room_type — Twin/Double saqlanadi), "
        "dublikatni o‘chiradi (is_active=False). Default: dry-run. "
        "--partial: overlap bo‘lsa ham mumkin bo‘lgan bronlarni ko‘chiradi."
    )

    def add_arguments(self, parser):
        parser.add_argument("--tenant", type=str, default="", help="Tenant slug yoki id")
        parser.add_argument("--property", type=str, default="", help="Property id yoki code")
        parser.add_argument(
            "--apply",
            action="store_true",
            help="O‘zgarishlarni saqlash (aks holda faqat ko‘rsatadi)",
        )
        parser.add_argument(
            "--partial",
            action="store_true",
            help="Overlap bronlarni SKIP qilmasdan, faqat bo‘sh kunlardagini ko‘chiradi",
        )

    def handle(self, *args, **options):
        tenant = self._resolve_tenant(options.get("tenant") or "")
        prop = self._resolve_property(tenant, options.get("property") or "")
        apply = bool(options.get("apply"))
        partial = bool(options.get("partial"))

        rooms_qs = Room.objects.filter(is_active=True).select_related(
            "room_type", "property", "tenant"
        )
        if tenant is not None:
            rooms_qs = rooms_qs.filter(tenant=tenant)
        if prop is not None:
            rooms_qs = rooms_qs.filter(property=prop)

        by_prop: dict[int, list[Room]] = defaultdict(list)
        for room in rooms_qs.order_by("property_id", "number"):
            by_prop[room.property_id].append(room)

        planned = 0
        merged = 0
        skipped = 0

        for prop_id, rooms in by_prop.items():
            by_base: dict[str, list[Room]] = defaultdict(list)
            keepers: dict[str, Room] = {}
            for room in rooms:
                base = base_number(room.number)
                if base:
                    by_base[base].append(room)
                else:
                    keepers[room.number] = room

            for base, dupes in sorted(by_base.items()):
                keeper = keepers.get(base)
                if keeper is None:
                    self.stdout.write(
                        self.style.WARNING(
                            f"[{prop_id}] {base}-* bor, lekin asosiy «{base}» yo‘q — o‘tkazildi"
                        )
                    )
                    skipped += len(dupes)
                    continue
                for dupe in dupes:
                    planned += 1
                    ok, detail = self._merge_pair(
                        keeper, dupe, apply=apply, partial=partial
                    )
                    if ok:
                        merged += 1
                        mark = "MERGED" if apply else "WOULD MERGE"
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"[{keeper.property.name}] {mark}: "
                                f"{dupe.number} ({dupe.room_type.name}) → "
                                f"{keeper.number} ({detail})"
                            )
                        )
                    else:
                        skipped += 1
                        self.stdout.write(
                            self.style.ERROR(
                                f"[{keeper.property.name}] SKIP {dupe.number} → "
                                f"{keeper.number}: {detail}"
                            )
                        )

        mode = "APPLY" if apply else "DRY-RUN"
        self.stdout.write(
            self.style.NOTICE(
                f"{mode}: planned={planned}, merged={merged}, skipped={skipped}"
            )
        )
        if not apply and planned:
            self.stdout.write("Haqiqiy birlashtirish: --apply")

    def _merge_pair(
        self, keeper: Room, dupe: Room, *, apply: bool, partial: bool
    ) -> tuple[bool, str]:
        if keeper.pk == dupe.pk:
            return False, "same room"
        if keeper.property_id != dupe.property_id:
            return False, "different property"

        blocking = []
        active = list(
            Reservation.objects.filter(room=dupe)
            .exclude(
                status__in=[
                    Reservation.Status.CANCELLED,
                    Reservation.Status.NO_SHOW,
                ]
            )
            .select_related("guest", "room_type")
            .order_by("check_in")
        )
        movable = []
        for res in active:
            try:
                assert_room_available(
                    keeper,
                    res.check_in,
                    res.check_out,
                    exclude_reservation_id=res.pk,
                )
            except AvailabilityError as exc:
                blocking.append(f"{res.code}: {'; '.join(exc.messages)}")
                continue
            movable.append(res)

        if blocking and not partial:
            return False, "; ".join(blocking[:3])

        types_to_add = []
        if dupe.room_type_id and not keeper.allows_room_type(dupe.room_type):
            types_to_add.append(dupe.room_type)
        for t in dupe.sellable_type_list():
            if not keeper.allows_room_type(t) and t not in types_to_add:
                types_to_add.append(t)

        left = len(blocking)
        mode = "PARTIAL" if blocking else "FULL"
        detail = (
            f"{mode} +types={[t.name for t in types_to_add] or ['(already)']}, "
            f"move={len(movable)}, left_on_dupe={left}"
        )
        if blocking:
            detail += f" blockers=[{'; '.join(blocking[:3])}]"
        if not apply:
            return True, detail

        with transaction.atomic():
            for t in types_to_add:
                keeper.sellable_types.add(t)
            keeper.ensure_primary_sellable()
            if hasattr(keeper, "_prefetched_objects_cache"):
                keeper._prefetched_objects_cache.pop("sellable_types", None)

            movable_ids = {r.pk for r in movable}
            for res in movable:
                sold_as = res.room_type
                res.room = keeper
                # Keep Twin/Double sold-as; only fall back if somehow invalid
                if sold_as and not keeper.allows_room_type(sold_as):
                    res.room_type = keeper.room_type
                res.save(update_fields=["room", "room_type", "updated_at"])

            # Move cancelled/no_show history to keeper; leave blocking active on dupe
            Reservation.objects.filter(room=dupe).filter(
                status__in=[
                    Reservation.Status.CANCELLED,
                    Reservation.Status.NO_SHOW,
                ]
            ).update(room=keeper)

            still_active = (
                Reservation.objects.filter(room=dupe)
                .exclude(
                    status__in=[
                        Reservation.Status.CANCELLED,
                        Reservation.Status.NO_SHOW,
                    ]
                )
                .count()
            )
            if still_active == 0:
                Reservation.objects.filter(room=dupe).update(room=keeper)
                dupe.is_active = False
                dupe.notes = (
                    (dupe.notes + " | " if dupe.notes else "")
                    + f"merged into {keeper.number}"
                )[:255]
                dupe.save(update_fields=["is_active", "notes", "updated_at"])
                detail += ", deactivated=yes"
            else:
                detail += f", deactivated=no (active_left={still_active})"
        return True, detail

    def _resolve_tenant(self, raw: str):
        raw = (raw or "").strip()
        if not raw:
            return None
        if raw.isdigit():
            tenant = Tenant.objects.filter(pk=int(raw)).first()
        else:
            tenant = Tenant.objects.filter(Q(slug=raw) | Q(name__iexact=raw)).first()
        if tenant is None:
            raise SystemExit(f"Tenant topilmadi: {raw}")
        return tenant

    def _resolve_property(self, tenant, raw: str):
        raw = (raw or "").strip()
        if not raw:
            return None
        qs = Property.objects.all()
        if tenant is not None:
            qs = qs.filter(tenant=tenant)
        if raw.isdigit():
            prop = qs.filter(pk=int(raw)).first()
        else:
            prop = qs.filter(Q(branch_code__iexact=raw) | Q(name__iexact=raw)).first()
        if prop is None:
            raise SystemExit(f"Property topilmadi: {raw}")
        return prop
