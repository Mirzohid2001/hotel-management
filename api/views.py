from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from bookings.models import Reservation
from bookings.services import (
    apply_amendment,
    cancel_reservation,
    check_in_reservation,
    check_out_reservation,
    create_reservation,
    mark_no_show,
    transfer_room,
)
from core.roles import (
    CASH,
    FLOOR_VIEW,
    FRONT_DESK_MONEY,
    FRONT_OFFICE,
    SERVICES,
    STAY_DESK,
)
from guests.models import Guest
from properties.models import Room
from tenants.models import TenantMembership

from .auth import (
    api_login_required,
    api_role_required,
    json_error,
    json_ok,
    me_payload,
    parse_json,
)
from .board import build_board
from .models import ApiToken

# Reception + housekeeping can flip room status on mobile board.
ROOM_STATUS_ROLES = (*FLOOR_VIEW, TenantMembership.Role.HOUSEKEEPER)


@csrf_exempt
@require_POST
def login(request):
    """POST {username, password, tenant_id?} → token + me."""
    data = parse_json(request)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return json_error("username and password required.")

    user = authenticate(request, username=username, password=password)
    if user is None or not user.is_active:
        return json_error("Invalid credentials.", status=401)

    memberships = list(
        TenantMembership.objects.filter(user=user, is_active=True, tenant__is_active=True)
        .select_related("tenant")
        .order_by("tenant__name")
    )
    if not memberships:
        return json_error("No active hotel membership.", status=403)

    tenant_id = data.get("tenant_id")
    if tenant_id is not None and tenant_id != "":
        try:
            tid = int(tenant_id)
        except (TypeError, ValueError):
            return json_error("Invalid tenant_id.")
        membership = next((m for m in memberships if m.tenant_id == tid), None)
        if membership is None:
            return json_error("Tenant not allowed for this user.", status=403)
    else:
        membership = memberships[0]

    ApiToken.objects.filter(
        user=user, tenant=membership.tenant, revoked_at__isnull=True, label="mobile"
    ).update(revoked_at=timezone.now())

    token = ApiToken.objects.create(user=user, tenant=membership.tenant, label="mobile")
    request.user = user
    request.membership = membership
    request.tenant = membership.tenant
    request.active_property = None

    return json_ok(
        {
            "token": token.key,
            "tenants": [
                {
                    "id": m.tenant_id,
                    "name": m.tenant.name,
                    "slug": m.tenant.slug,
                    "role": m.role,
                }
                for m in memberships
            ],
            "me": me_payload(request),
        }
    )


@api_login_required
@require_POST
def logout(request):
    token = getattr(request, "api_token", None)
    if token is not None:
        token.revoke()
    return json_ok({"revoked": True})


@api_login_required
@require_GET
def me(request):
    return json_ok(me_payload(request))


@api_login_required
@api_role_required(*FLOOR_VIEW)
@require_GET
def board(request):
    day = timezone.localdate()
    day_s = request.GET.get("date")
    if day_s:
        try:
            day = date.fromisoformat(day_s)
        except ValueError:
            return json_error("Invalid date (use YYYY-MM-DD).")
    hotel = getattr(request, "active_property", None)
    return json_ok(build_board(tenant=request.tenant, hotel=hotel, day=day))


def _get_reservation(request, pk: int) -> Reservation | None:
    return (
        Reservation.objects.filter(pk=pk, tenant=request.tenant)
        .select_related("guest", "room", "hotel")
        .first()
    )


def _reservation_summary(reservation: Reservation) -> dict:
    return {
        "id": reservation.pk,
        "code": reservation.code,
        "status": reservation.status,
        "check_in": reservation.check_in.isoformat(),
        "check_out": reservation.check_out.isoformat(),
        "adults": reservation.adults,
        "children": reservation.children,
        "guest": {
            "id": reservation.guest_id,
            "name": str(reservation.guest) if reservation.guest_id else "",
        },
        "room": {
            "id": reservation.room_id,
            "number": reservation.room.number if reservation.room_id else "",
        },
        "hotel_id": reservation.hotel_id,
    }


def _base_reservations(request):
    qs = Reservation.objects.filter(tenant=request.tenant).select_related(
        "guest", "room", "hotel"
    )
    hotel = getattr(request, "active_property", None)
    if hotel is not None:
        qs = qs.filter(hotel=hotel)
    return qs


@api_login_required
@api_role_required(*FLOOR_VIEW)
@require_GET
def today(request):
    """Arrivals, departures, and in-house for a day."""
    day = timezone.localdate()
    day_s = request.GET.get("date")
    if day_s:
        try:
            day = date.fromisoformat(day_s)
        except ValueError:
            return json_error("Invalid date (use YYYY-MM-DD).")

    base = _base_reservations(request)
    arrivals = list(
        base.filter(
            check_in=day,
            status__in=[
                Reservation.Status.CONFIRMED,
                Reservation.Status.CHECKED_IN,
            ],
        ).order_by("room__number", "code")[:200]
    )
    departures = list(
        base.filter(
            check_out=day,
            status=Reservation.Status.CHECKED_IN,
        ).order_by("room__number", "code")[:200]
    )
    in_house = list(
        base.filter(status=Reservation.Status.CHECKED_IN).order_by(
            "room__number", "code"
        )[:200]
    )
    return json_ok(
        {
            "day": day.isoformat(),
            "arrivals": [_reservation_summary(r) for r in arrivals],
            "departures": [_reservation_summary(r) for r in departures],
            "in_house": [_reservation_summary(r) for r in in_house],
            "counts": {
                "arrivals": len(arrivals),
                "departures": len(departures),
                "in_house": len(in_house),
            },
        }
    )


@api_login_required
@api_role_required(*FLOOR_VIEW)
@require_GET
def reservation_search(request):
    """Search reservations by code, guest name/phone, or room number."""
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return json_error("q must be at least 2 characters.")
    qs = (
        _base_reservations(request)
        .filter(
            Q(code__icontains=q)
            | Q(guest__first_name__icontains=q)
            | Q(guest__last_name__icontains=q)
            | Q(guest__phone__icontains=q)
            | Q(room__number__icontains=q)
        )
        .distinct()
        .order_by("-check_in", "-pk")[:50]
    )
    return json_ok({"q": q, "items": [_reservation_summary(r) for r in qs]})


def _folio_payload(folio_obj) -> dict | None:
    if folio_obj is None:
        return None
    charges = [
        {
            "id": c.pk,
            "charge_type": c.charge_type,
            "description": c.description,
            "quantity": str(c.quantity),
            "unit_price": str(c.unit_price),
            "amount": str(c.amount),
            "is_void": c.is_void,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in folio_obj.charges.filter(is_void=False).order_by("created_at")
    ]
    payments = [
        {
            "id": p.pk,
            "amount": str(p.amount),
            "method": p.method,
            "kind": p.kind,
            "is_void": p.is_void,
            "note": p.note or "",
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in folio_obj.payments.filter(is_void=False).order_by("created_at")
    ]
    return {
        "id": folio_obj.pk,
        "balance": str(folio_obj.balance),
        "is_open": folio_obj.is_open,
        "charges": charges,
        "payments": payments,
    }


@api_login_required
@api_role_required(*FLOOR_VIEW)
@require_GET
def reservation_detail(request, pk):
    reservation = _get_reservation(request, pk)
    if reservation is None:
        return json_error("Reservation not found.", status=404)
    try:
        folio_obj = reservation.folio
    except Exception:
        folio_obj = None
    return json_ok(
        {
            "id": reservation.pk,
            "code": reservation.code,
            "status": reservation.status,
            "check_in": reservation.check_in.isoformat(),
            "check_out": reservation.check_out.isoformat(),
            "adults": reservation.adults,
            "children": reservation.children,
            "guest": {
                "id": reservation.guest_id,
                "name": str(reservation.guest) if reservation.guest_id else "",
            },
            "room": {
                "id": reservation.room_id,
                "number": reservation.room.number if reservation.room_id else "",
                "status": reservation.room.status if reservation.room_id else "",
            },
            "hotel_id": reservation.hotel_id,
            "notes": reservation.notes or "",
            "nightly_rate": str(reservation.nightly_rate)
            if reservation.nightly_rate is not None
            else "",
            "folio": _folio_payload(folio_obj),
        }
    )


@api_login_required
@api_role_required(*STAY_DESK)
@require_POST
def reservation_check_in(request, pk):
    reservation = _get_reservation(request, pk)
    if reservation is None:
        return json_error("Reservation not found.", status=404)
    data = parse_json(request)
    allow_dirty = bool(data.get("allow_dirty"))
    allow_no_docs = bool(data.get("allow_no_docs"))
    collect_emehmon = data.get("collect_emehmon", True)
    try:
        check_in_reservation(
            reservation,
            request.user,
            allow_dirty=allow_dirty,
            allow_no_docs=allow_no_docs,
        )
        reservation.refresh_from_db()
        emehmon_note = None
        if collect_emehmon:
            from folio.services import collect_emehmon_fee, default_emehmon_fee

            if not reservation.emehmon_required:
                reservation.emehmon_required = True
                reservation.save(update_fields=["emehmon_required", "updated_at"])
            try:
                collect_emehmon_fee(
                    reservation,
                    request.user,
                    amount=default_emehmon_fee(reservation),
                    method=data.get("emehmon_method") or "cash",
                )
                emehmon_note = "collected"
            except ValidationError as exc:
                emehmon_note = "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
        return json_ok(
            {
                "reservation_id": reservation.pk,
                "status": reservation.status,
                "emehmon": emehmon_note,
            }
        )
    except ValidationError as exc:
        return json_error(
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
            status=400,
        )


@api_login_required
@api_role_required(*STAY_DESK)
@require_POST
def reservation_check_out(request, pk):
    reservation = _get_reservation(request, pk)
    if reservation is None:
        return json_error("Reservation not found.", status=404)
    try:
        check_out_reservation(reservation, request.user)
        reservation.refresh_from_db()
        return json_ok({"reservation_id": reservation.pk, "status": reservation.status})
    except ValidationError as exc:
        return json_error(
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
            status=400,
        )


@api_login_required
@api_role_required(*FRONT_OFFICE)
@require_POST
def walk_in(request):
    """Create guest + reservation + check-in for a vacant room."""
    data = parse_json(request)
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)

    room_id = data.get("room_id")
    first_name = (data.get("first_name") or "").strip()
    if not room_id or not first_name:
        return json_error("room_id and first_name required.")

    try:
        nights = max(1, int(data.get("nights") or 1))
        adults = max(1, int(data.get("adults") or 1))
        children = max(0, int(data.get("children") or 0))
    except (TypeError, ValueError):
        return json_error("Invalid nights/adults/children.")

    room = Room.objects.filter(
        pk=room_id, tenant=request.tenant, property=hotel, is_active=True
    ).select_related("room_type").first()
    if room is None:
        return json_error("Room not found.", status=404)

    today = timezone.localdate()
    allow_dirty = bool(data.get("allow_dirty"))
    allow_no_docs = bool(data.get("allow_no_docs"))
    collect_emehmon = data.get("collect_emehmon", True)
    doc_number = (data.get("doc_number") or "").strip()

    try:
        guest = Guest.objects.create(
            tenant=request.tenant,
            first_name=first_name,
            last_name=(data.get("last_name") or "").strip(),
            phone=(data.get("phone") or "").strip(),
        )
        if doc_number:
            from guests.models import GuestDocument

            GuestDocument.objects.create(
                tenant=request.tenant,
                guest=guest,
                doc_type=data.get("doc_type") or GuestDocument.DocType.PASSPORT,
                number=doc_number,
            )

        nightly = data.get("nightly_rate")
        nightly_rate = None
        if nightly not in (None, ""):
            nightly_rate = Decimal(str(nightly).replace(",", "."))

        reservation = create_reservation(
            tenant=request.tenant,
            user=request.user,
            property_obj=hotel,
            guest=guest,
            room_type=room.room_type,
            room=room,
            nightly_rate=nightly_rate,
            check_in=today,
            check_out=today + timedelta(days=nights),
            adults=adults,
            children=children,
            source=Reservation.Source.WALKIN,
            notes=(data.get("notes") or "").strip(),
            emehmon_required=bool(collect_emehmon),
        )
        check_in_reservation(
            reservation,
            request.user,
            allow_dirty=allow_dirty,
            allow_no_docs=allow_no_docs or not doc_number,
        )
        reservation.refresh_from_db()
        emehmon_note = None
        if collect_emehmon:
            from folio.services import collect_emehmon_fee, default_emehmon_fee

            try:
                collect_emehmon_fee(
                    reservation,
                    request.user,
                    amount=default_emehmon_fee(reservation),
                    method=data.get("emehmon_method") or "cash",
                )
                emehmon_note = "collected"
            except ValidationError as exc:
                emehmon_note = (
                    "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
                )
        return json_ok(
            {
                "reservation_id": reservation.pk,
                "code": reservation.code,
                "status": reservation.status,
                "emehmon": emehmon_note,
            },
            status=201,
        )
    except ValidationError as exc:
        return json_error(
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
            status=400,
        )
    except InvalidOperation:
        return json_error("Invalid nightly_rate.")


@api_login_required
@api_role_required(*FRONT_DESK_MONEY)
@require_POST
def reservation_payment(request, pk):
    """Post a guest payment on the reservation folio."""
    reservation = _get_reservation(request, pk)
    if reservation is None:
        return json_error("Reservation not found.", status=404)
    data = parse_json(request)
    try:
        amount = Decimal(str(data.get("amount", "")).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return json_error("Valid amount required.")
    if amount <= 0:
        return json_error("Amount must be positive.")

    method = (data.get("method") or "cash").strip().lower()
    if method not in ("cash", "card", "transfer"):
        return json_error("method must be cash, card, or transfer.")

    try:
        from folio.models import GuestPayment
        from folio.services import add_payment, ensure_folio_for_reservation

        folio = ensure_folio_for_reservation(reservation, allow_pre_checkin=True)
        payment = add_payment(
            folio,
            request.user,
            amount=amount,
            method=method,
            note=(data.get("note") or "").strip(),
            kind=GuestPayment.Kind.PAYMENT,
        )
        folio.refresh_from_db()
        return json_ok(
            {
                "payment_id": payment.pk,
                "amount": str(payment.amount),
                "method": payment.method,
                "balance": str(folio.balance),
            },
            status=201,
        )
    except ValidationError as exc:
        return json_error(
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
            status=400,
        )


@api_login_required
@api_role_required(*ROOM_STATUS_ROLES)
@require_POST
def room_set_status(request, pk):
    """Set room housekeeping status (ready / dirty / cleaning / …)."""
    hotel = getattr(request, "active_property", None)
    qs = Room.objects.filter(pk=pk, tenant=request.tenant, is_active=True)
    if hotel is not None:
        qs = qs.filter(property=hotel)
    room = qs.first()
    if room is None:
        return json_error("Room not found.", status=404)

    data = parse_json(request)
    new_status = (data.get("status") or "").strip()
    if new_status not in dict(Room.Status.choices):
        return json_error(
            "status must be one of: " + ", ".join(dict(Room.Status.choices))
        )

    from housekeeping.models import HousekeepingTask
    from housekeeping.services import set_room_status

    set_room_status(
        room,
        new_status,
        user=request.user,
        note=(data.get("note") or "").strip(),
    )
    if new_status == Room.Status.DIRTY:
        HousekeepingTask.objects.create(
            tenant=request.tenant,
            room=room,
            title="Tozalash",
        )
    room.refresh_from_db()
    return json_ok(
        {
            "room_id": room.pk,
            "number": room.number,
            "status": room.status,
        }
    )


@api_login_required
@api_role_required(*FRONT_DESK_MONEY)
@require_POST
def reservation_charge(request, pk):
    """Post a manual folio charge."""
    reservation = _get_reservation(request, pk)
    if reservation is None:
        return json_error("Reservation not found.", status=404)
    data = parse_json(request)
    description = (data.get("description") or "").strip()
    if not description:
        return json_error("description required.")
    try:
        unit_price = Decimal(str(data.get("unit_price", "")).replace(",", "."))
        quantity = Decimal(str(data.get("quantity") or "1").replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return json_error("Valid unit_price (and quantity) required.")
    if unit_price < 0 or quantity <= 0:
        return json_error("unit_price >= 0 and quantity > 0 required.")

    from folio.models import FolioCharge
    from folio.services import add_charge, ensure_folio_for_reservation

    charge_type = (data.get("charge_type") or FolioCharge.ChargeType.OTHER).strip()
    if charge_type not in dict(FolioCharge.ChargeType.choices):
        return json_error("Invalid charge_type.")

    try:
        folio = ensure_folio_for_reservation(reservation, allow_pre_checkin=True)
        charge = add_charge(
            folio,
            request.user,
            charge_type=charge_type,
            description=description,
            unit_price=unit_price,
            quantity=quantity,
        )
        folio.refresh_from_db()
        return json_ok(
            {
                "charge_id": charge.pk,
                "amount": str(charge.amount),
                "balance": str(folio.balance),
            },
            status=201,
        )
    except ValidationError as exc:
        return json_error(
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
            status=400,
        )


@api_login_required
@api_role_required(*SERVICES)
@require_GET
def service_list(request):
    from services.models import ServiceItem

    items = ServiceItem.objects.filter(tenant=request.tenant, is_active=True).order_by(
        "name"
    )
    return json_ok(
        {
            "items": [
                {
                    "id": s.pk,
                    "name": s.name,
                    "code": s.code,
                    "unit_price": str(s.unit_price),
                    "currency": s.currency,
                }
                for s in items
            ]
        }
    )


@api_login_required
@api_role_required(*SERVICES)
@require_POST
def reservation_service(request, pk):
    """Order a catalog service onto the reservation folio."""
    reservation = _get_reservation(request, pk)
    if reservation is None:
        return json_error("Reservation not found.", status=404)
    data = parse_json(request)
    service_id = data.get("service_id")
    if not service_id:
        return json_error("service_id required.")
    try:
        quantity = Decimal(str(data.get("quantity") or "1").replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return json_error("Invalid quantity.")
    if quantity <= 0:
        return json_error("quantity must be positive.")

    from services.models import ServiceItem
    from services.services import order_service

    service = ServiceItem.objects.filter(
        pk=service_id, tenant=request.tenant, is_active=True
    ).first()
    if service is None:
        return json_error("Service not found.", status=404)

    try:
        order = order_service(
            reservation=reservation,
            service=service,
            user=request.user,
            quantity=quantity,
            note=(data.get("note") or "").strip(),
        )
        balance = None
        try:
            balance = str(reservation.folio.balance)
        except Exception:
            pass
        return json_ok(
            {
                "order_id": order.pk,
                "service": service.name,
                "amount": str(order.amount),
                "balance": balance,
            },
            status=201,
        )
    except ValidationError as exc:
        return json_error(
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
            status=400,
        )


@api_login_required
@api_role_required(*STAY_DESK)
@require_POST
def reservation_transfer(request, pk):
    """Move a checked-in guest to another room."""
    reservation = _get_reservation(request, pk)
    if reservation is None:
        return json_error("Reservation not found.", status=404)
    data = parse_json(request)
    room_id = data.get("room_id")
    if not room_id:
        return json_error("room_id required.")
    hotel = getattr(request, "active_property", None) or reservation.hotel
    room = Room.objects.filter(
        pk=room_id, tenant=request.tenant, is_active=True
    ).first()
    if room is None:
        return json_error("Room not found.", status=404)
    if hotel is not None and room.property_id != hotel.pk:
        return json_error("Room belongs to another hotel.", status=400)
    try:
        transfer_room(
            reservation,
            request.user,
            room,
            reason=(data.get("reason") or "").strip(),
        )
        reservation.refresh_from_db()
        return json_ok(
            {
                "reservation_id": reservation.pk,
                "room": {
                    "id": reservation.room_id,
                    "number": reservation.room.number if reservation.room_id else "",
                },
                "status": reservation.status,
            }
        )
    except ValidationError as exc:
        return json_error(
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
            status=400,
        )


@api_login_required
@api_role_required(*STAY_DESK)
@require_POST
def reservation_extend(request, pk):
    """Extend stay by N nights (default 1)."""
    reservation = _get_reservation(request, pk)
    if reservation is None:
        return json_error("Reservation not found.", status=404)
    if reservation.status not in (
        Reservation.Status.CONFIRMED,
        Reservation.Status.CHECKED_IN,
    ):
        return json_error("Only confirmed or checked-in stays can be extended.")
    data = parse_json(request)
    try:
        nights = max(1, int(data.get("nights") or 1))
    except (TypeError, ValueError):
        return json_error("Invalid nights.")
    new_out = reservation.check_out + timedelta(days=nights)
    try:
        apply_amendment(
            reservation,
            request.user,
            {
                "check_in": reservation.check_in,
                "check_out": new_out,
                "room": reservation.room,
                "rate_plan": reservation.rate_plan,
                "nightly_rate": reservation.nightly_rate,
                "adults": reservation.adults,
                "children": reservation.children,
                "reason": (data.get("reason") or "extend").strip() or "extend",
            },
        )
        reservation.refresh_from_db()
        return json_ok(
            {
                "reservation_id": reservation.pk,
                "check_in": reservation.check_in.isoformat(),
                "check_out": reservation.check_out.isoformat(),
                "status": reservation.status,
            }
        )
    except ValidationError as exc:
        return json_error(
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
            status=400,
        )


@api_login_required
@api_role_required(*STAY_DESK)
@require_POST
def reservation_cancel(request, pk):
    reservation = _get_reservation(request, pk)
    if reservation is None:
        return json_error("Reservation not found.", status=404)
    data = parse_json(request)
    try:
        cancel_reservation(
            reservation, request.user, reason=(data.get("reason") or "").strip()
        )
        reservation.refresh_from_db()
        return json_ok(
            {"reservation_id": reservation.pk, "status": reservation.status}
        )
    except ValidationError as exc:
        return json_error(
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
            status=400,
        )


@api_login_required
@api_role_required(*STAY_DESK)
@require_POST
def reservation_no_show(request, pk):
    reservation = _get_reservation(request, pk)
    if reservation is None:
        return json_error("Reservation not found.", status=404)
    data = parse_json(request)
    try:
        mark_no_show(
            reservation, request.user, reason=(data.get("reason") or "").strip()
        )
        reservation.refresh_from_db()
        return json_ok(
            {"reservation_id": reservation.pk, "status": reservation.status}
        )
    except ValidationError as exc:
        return json_error(
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
            status=400,
        )


@api_login_required
@api_role_required(*FLOOR_VIEW)
@require_GET
def rooms_available(request):
    """Rooms free for [check_in, check_out)."""
    try:
        check_in = date.fromisoformat((request.GET.get("check_in") or "").strip())
        check_out = date.fromisoformat((request.GET.get("check_out") or "").strip())
    except ValueError:
        return json_error("check_in and check_out required (YYYY-MM-DD).")
    if check_out <= check_in:
        return json_error("check_out must be after check_in.")

    hotel = getattr(request, "active_property", None)
    rooms = Room.objects.filter(
        tenant=request.tenant, is_active=True
    ).exclude(status=Room.Status.OUT_OF_ORDER).select_related("room_type", "property")
    if hotel is not None:
        rooms = rooms.filter(property=hotel)

    from bookings.models import Reservation as Res

    busy_ids = set(
        Res.objects.filter(tenant=request.tenant)
        .overlapping(check_in, check_out)
        .exclude(room_id=None)
        .values_list("room_id", flat=True)
    )
    items = []
    for room in rooms.order_by("number"):
        if room.pk in busy_ids:
            continue
        items.append(
            {
                "id": room.pk,
                "number": room.number,
                "status": room.status,
                "room_type": room.room_type.name if room.room_type_id else "",
                "room_type_id": room.room_type_id,
                "hotel_id": room.property_id,
                "base_price": str(room.room_type.base_price)
                if room.room_type_id
                else "0",
            }
        )
    return json_ok(
        {
            "check_in": check_in.isoformat(),
            "check_out": check_out.isoformat(),
            "items": items,
        }
    )


@api_login_required
@api_role_required(*FRONT_OFFICE)
@require_POST
def reservation_create(request):
    """Advance booking (confirmed, no immediate check-in)."""
    data = parse_json(request)
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)

    first_name = (data.get("first_name") or "").strip()
    room_id = data.get("room_id")
    if not first_name or not room_id:
        return json_error("first_name and room_id required.")

    try:
        check_in = date.fromisoformat(str(data.get("check_in") or "").strip())
        check_out = date.fromisoformat(str(data.get("check_out") or "").strip())
    except ValueError:
        return json_error("Valid check_in and check_out (YYYY-MM-DD) required.")
    if check_out <= check_in:
        return json_error("check_out must be after check_in.")

    try:
        adults = max(1, int(data.get("adults") or 1))
        children = max(0, int(data.get("children") or 0))
    except (TypeError, ValueError):
        return json_error("Invalid adults/children.")

    room = Room.objects.filter(
        pk=room_id, tenant=request.tenant, property=hotel, is_active=True
    ).select_related("room_type").first()
    if room is None:
        return json_error("Room not found.", status=404)

    nightly = data.get("nightly_rate")
    nightly_rate = None
    if nightly not in (None, ""):
        try:
            nightly_rate = Decimal(str(nightly).replace(",", "."))
        except (InvalidOperation, TypeError, ValueError):
            return json_error("Invalid nightly_rate.")

    try:
        guest = Guest.objects.create(
            tenant=request.tenant,
            first_name=first_name,
            last_name=(data.get("last_name") or "").strip(),
            phone=(data.get("phone") or "").strip(),
        )
        reservation = create_reservation(
            tenant=request.tenant,
            user=request.user,
            property_obj=hotel,
            guest=guest,
            room_type=room.room_type,
            room=room,
            nightly_rate=nightly_rate,
            check_in=check_in,
            check_out=check_out,
            adults=adults,
            children=children,
            source=data.get("source") or Reservation.Source.PHONE,
            notes=(data.get("notes") or "").strip(),
            emehmon_required=bool(data.get("emehmon_required", True)),
        )
        return json_ok(
            {
                "reservation_id": reservation.pk,
                "code": reservation.code,
                "status": reservation.status,
                "check_in": reservation.check_in.isoformat(),
                "check_out": reservation.check_out.isoformat(),
            },
            status=201,
        )
    except ValidationError as exc:
        return json_error(
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
            status=400,
        )


def _shift_payload(shift) -> dict:
    from folio.services import expected_cash_in_shift

    expected = None
    if shift.is_open:
        try:
            expected = str(expected_cash_in_shift(shift))
        except Exception:
            expected = None
    return {
        "id": shift.pk,
        "is_open": shift.is_open,
        "hotel_id": shift.hotel_id,
        "opening_float": str(shift.opening_float),
        "opened_at": shift.opened_at.isoformat() if shift.opened_at else None,
        "closed_at": shift.closed_at.isoformat() if shift.closed_at else None,
        "closing_cash": str(shift.closing_cash) if shift.closing_cash is not None else None,
        "variance": str(shift.variance) if shift.variance is not None else None,
        "expected_cash": expected,
        "notes": shift.notes or "",
    }


@api_login_required
@api_role_required(*CASH)
@require_GET
def cash_shift_status(request):
    from folio.services import get_open_shift

    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    shift = get_open_shift(request.tenant, hotel=hotel)
    return json_ok({"shift": _shift_payload(shift) if shift else None})


@api_login_required
@api_role_required(*CASH)
@require_POST
def cash_shift_open(request):
    from folio.services import open_cash_shift

    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    data = parse_json(request)
    try:
        opening = Decimal(str(data.get("opening_float") or "0").replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return json_error("Invalid opening_float.")
    if opening < 0:
        return json_error("opening_float must be >= 0.")
    try:
        shift = open_cash_shift(
            request.tenant, request.user, opening, hotel=hotel
        )
        return json_ok({"shift": _shift_payload(shift)}, status=201)
    except ValidationError as exc:
        return json_error(
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
            status=400,
        )


@api_login_required
@api_role_required(*CASH)
@require_POST
def cash_shift_close(request):
    from folio.services import close_cash_shift, get_open_shift

    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    shift = get_open_shift(request.tenant, hotel=hotel)
    if shift is None:
        return json_error("No open cash shift.", status=400)
    data = parse_json(request)
    try:
        closing = Decimal(str(data.get("closing_cash", "")).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return json_error("Valid closing_cash required.")
    if closing < 0:
        return json_error("closing_cash must be >= 0.")
    try:
        closed = close_cash_shift(
            shift,
            request.user,
            closing,
            notes=(data.get("notes") or "").strip(),
        )
        return json_ok({"shift": _shift_payload(closed)})
    except ValidationError as exc:
        return json_error(
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
            status=400,
        )


@api_login_required
@api_role_required(*STAY_DESK)
@require_POST
def reservation_notes(request, pk):
    reservation = _get_reservation(request, pk)
    if reservation is None:
        return json_error("Reservation not found.", status=404)
    if reservation.status in (
        Reservation.Status.CANCELLED,
        Reservation.Status.CHECKED_OUT,
        Reservation.Status.NO_SHOW,
    ):
        return json_error("Cannot edit notes on a closed reservation.")
    data = parse_json(request)
    notes = (data.get("notes") or "").strip()
    reservation.notes = notes
    reservation.save(update_fields=["notes", "updated_at"])
    return json_ok({"reservation_id": reservation.pk, "notes": reservation.notes})
