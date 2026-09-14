"""Named occupants for a room stay (primary guest + companions)."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext as _

from guests.models import Guest, GuestDocument

from .models import ReservationOccupant


class MissingOccupantsError(ValidationError):
    """Check-in blocked: occupancy count is higher than named people."""


def occupant_expected_count(reservation) -> int:
    return max(1, int(reservation.adults or 1) + int(reservation.children or 0))


def occupant_missing_slots(reservation) -> tuple[int, int]:
    """How many extra adult/child cards still need to be filled."""
    named = list(occupants_qs(reservation))
    named_adults = sum(
        1 for occ in named if occ.kind != ReservationOccupant.Kind.CHILD
    )
    named_children = sum(
        1 for occ in named if occ.kind == ReservationOccupant.Kind.CHILD
    )
    missing_adults = max(0, int(reservation.adults or 1) - named_adults)
    missing_children = max(0, int(reservation.children or 0) - named_children)
    return missing_adults, missing_children


def occupants_qs(reservation):
    return reservation.occupants.select_related("guest").prefetch_related(
        "guest__documents"
    ).order_by(
        "-is_primary", "sort_order", "id"
    )


def guest_document_number(guest) -> str:
    if guest is None:
        return ""
    doc = (
        guest.documents.filter(
            doc_type__in=[GuestDocument.DocType.PASSPORT, GuestDocument.DocType.ID_CARD]
        )
        .order_by("-id")
        .first()
    )
    return doc.number if doc else ""


def _attach_document(tenant, guest, *, doc_type, number, issued_country=""):
    number = (number or "").strip()
    if not number or guest is None:
        return
    exists = guest.documents.filter(number__iexact=number).exists()
    if exists:
        return
    GuestDocument.objects.create(
        tenant=tenant,
        guest=guest,
        doc_type=doc_type or GuestDocument.DocType.PASSPORT,
        number=number,
        issued_country=(issued_country or "").strip(),
    )


def find_guest_by_document(tenant, number: str):
    number = (number or "").strip()
    if not number:
        return None
    doc = (
        GuestDocument.objects.filter(tenant=tenant, number__iexact=number)
        .select_related("guest")
        .order_by("-id")
        .first()
    )
    return doc.guest if doc else None


def resolve_occupant_guest(tenant, row: dict) -> Guest:
    """Reuse existing guest (picker or passport), otherwise create."""
    guest = row.get("guest")
    first_name = (row.get("first_name") or "").strip()
    last_name = (row.get("last_name") or "").strip()
    phone = (row.get("phone") or "").strip()
    nationality = (row.get("nationality") or "").strip()
    doc_type = row.get("doc_type") or GuestDocument.DocType.PASSPORT
    doc_number = (row.get("doc_number") or "").strip()
    issued_country = (row.get("issued_country") or "").strip()

    if guest is None and doc_number:
        guest = find_guest_by_document(tenant, doc_number)

    if guest is None:
        if not first_name:
            raise ValidationError(_("Hamrohning ismini kiriting."))
        guest = Guest.objects.create(
            tenant=tenant,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            nationality=nationality or issued_country,
        )
    else:
        updates = []
        if first_name and not guest.first_name:
            guest.first_name = first_name
            updates.append("first_name")
        if last_name and not guest.last_name:
            guest.last_name = last_name
            updates.append("last_name")
        if phone and not guest.phone:
            guest.phone = phone
            updates.append("phone")
        if nationality and not guest.nationality:
            guest.nationality = nationality
            updates.append("nationality")
        if updates:
            guest.save(update_fields=[*updates, "updated_at"])

    if getattr(guest, "is_blacklisted", False):
        reason = getattr(guest, "blacklist_reason", "") or "blacklisted"
        raise ValidationError(_("Mehmon qora ro‘yxatda: %(r)s") % {"r": reason})

    _attach_document(
        tenant,
        guest,
        doc_type=doc_type,
        number=doc_number,
        issued_country=issued_country,
    )
    return guest


def _kind_of(row: dict) -> str:
    kind = row.get("kind") or ReservationOccupant.Kind.ADULT
    if kind not in {ReservationOccupant.Kind.ADULT, ReservationOccupant.Kind.CHILD}:
        return ReservationOccupant.Kind.ADULT
    return kind


@transaction.atomic
def ensure_primary_occupant(reservation) -> ReservationOccupant:
    """Guarantee the paying guest is listed as the primary occupant."""
    if reservation.guest_id is None:
        raise ValidationError(_("Bron mehmonsiz bo‘lishi mumkin emas."))
    primary = reservation.occupants.filter(is_primary=True).select_related("guest").first()
    if primary and primary.guest_id == reservation.guest_id:
        return primary
    if primary and primary.guest_id != reservation.guest_id:
        primary.is_primary = False
        primary.save(update_fields=["is_primary", "updated_at"])
    existing = reservation.occupants.filter(guest_id=reservation.guest_id).first()
    if existing:
        existing.is_primary = True
        existing.kind = ReservationOccupant.Kind.ADULT
        existing.sort_order = 0
        existing.save(update_fields=["is_primary", "kind", "sort_order", "updated_at"])
        return existing
    return ReservationOccupant.objects.create(
        tenant=reservation.tenant,
        reservation=reservation,
        guest=reservation.guest,
        kind=ReservationOccupant.Kind.ADULT,
        is_primary=True,
        sort_order=0,
    )


@transaction.atomic
def sync_reservation_occupants(reservation, companions=None, *, primary_guest=None):
    """Replace named occupants. Primary is always reservation.guest (or override)."""
    if primary_guest is not None:
        reservation.guest = primary_guest
    if reservation.guest_id is None:
        raise ValidationError(_("Bron mehmonsiz bo‘lishi mumkin emas."))
    if getattr(reservation.guest, "is_blacklisted", False):
        reason = getattr(reservation.guest, "blacklist_reason", "") or "blacklisted"
        raise ValidationError(
            _("Mehmon qora ro‘yxatda: %(r)s") % {"r": reason}
        )

    companions = list(companions or [])
    resolved = []
    seen = {reservation.guest_id}
    extra_adults = 0
    extra_children = 0
    for row in companions:
        # Bo‘sh formset qatorlari (faqat UZ default) — e’tiborsiz.
        if not row:
            continue
        if not (
            row.get("guest")
            or (row.get("first_name") or "").strip()
            or (row.get("last_name") or "").strip()
            or (row.get("doc_number") or "").strip()
            or (row.get("phone") or "").strip()
        ):
            continue
        guest = resolve_occupant_guest(reservation.tenant, row)
        if guest.pk in seen:
            raise ValidationError(
                _("«%(name)s» allaqachon xonada — boshqa kishini kiriting.")
                % {"name": guest.full_name}
            )
        seen.add(guest.pk)
        kind = _kind_of(row)
        resolved.append((guest, kind))
        if kind == ReservationOccupant.Kind.CHILD:
            extra_children += 1
        else:
            extra_adults += 1

    reservation.occupants.all().delete()
    ReservationOccupant.objects.create(
        tenant=reservation.tenant,
        reservation=reservation,
        guest=reservation.guest,
        kind=ReservationOccupant.Kind.ADULT,
        is_primary=True,
        sort_order=0,
    )
    for index, (guest, kind) in enumerate(resolved, start=1):
        ReservationOccupant.objects.create(
            tenant=reservation.tenant,
            reservation=reservation,
            guest=guest,
            kind=kind,
            is_primary=False,
            sort_order=index,
        )

    reservation.adults = max(int(reservation.adults or 1), 1 + extra_adults)
    reservation.children = max(int(reservation.children or 0), extra_children)
    reservation.save(update_fields=["guest", "adults", "children", "updated_at"])
    return reservation


def assert_occupants_ready_for_checkin(reservation, *, allow_no_docs=False):
    """Named people must match headcount; IDs if the hotel requires them."""
    from .services import guest_has_id_document

    ensure_primary_occupant(reservation)
    named = list(occupants_qs(reservation))
    expected = occupant_expected_count(reservation)
    if len(named) < expected:
        raise MissingOccupantsError(
            _(
                "Xonada %(n)s kishi ko‘rsatilgan, lekin faqat %(k)s kishining "
                "ma’lumoti bor. Joylashdan oldin barcha mehmonlarni kiriting."
            )
            % {"n": expected, "k": len(named)}
        )
    missing_docs = []
    for occ in named:
        guest = occ.guest
        if guest.is_blacklisted:
            reason = guest.blacklist_reason or "blacklisted"
            raise ValidationError(
                _("«%(name)s» qora ro‘yxatda: %(r)s")
                % {"name": guest.full_name, "r": reason}
            )
        if not guest_has_id_document(guest):
            missing_docs.append(guest.full_name)
    if missing_docs and not allow_no_docs:
        from .services import MissingGuestDocsError

        names = ", ".join(missing_docs)
        raise MissingGuestDocsError(
            _("Pasport/ID yo‘q: %(names)s. Hujjat qo‘shing yoki hujjat ruxsatini bering.")
            % {"names": names}
        )
    return named


def reservations_for_guest(tenant, guest):
    """Primary or companion stays for this guest profile."""
    from .models import Reservation

    return (
        Reservation.objects.filter(tenant=tenant)
        .filter(Q(guest=guest) | Q(occupants__guest=guest))
        .distinct()
    )
