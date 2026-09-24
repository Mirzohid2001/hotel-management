"""Extra front-desk / ops API endpoints — web services reused, HTML untouched."""

from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.views.decorators.http import require_GET, require_POST

from bookings.models import Reservation
from bookings.services import apply_amendment, confirm_inquiry
from core.roles import (
    CASH,
    DASHBOARD,
    FLOOR_VIEW,
    FRONT_DESK_MONEY,
    FRONT_OFFICE,
    HOUSEKEEPING,
    INVENTORY,
    MONEY_VOID,
    OPS_MANAGER,
    STAY_DESK,
)
from guests.models import Guest
from properties.models import Room
from tenants.models import TenantMembership

from .auth import api_login_required, api_role_required, json_error, json_ok, parse_json
from .views import ROOM_STATUS_ROLES, _get_reservation, _reservation_summary


@api_login_required
@api_role_required(*FRONT_DESK_MONEY)
@require_POST
def reservation_deposit(request, pk):
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
        from folio.services import add_payment, open_folio_for_deposit

        folio = open_folio_for_deposit(reservation, request.user)
        payment = add_payment(
            folio,
            request.user,
            amount=amount,
            method=method,
            note=(data.get("note") or "").strip() or "Depozit",
            kind=GuestPayment.Kind.DEPOSIT,
        )
        folio.refresh_from_db()
        return json_ok(
            {
                "payment_id": payment.pk,
                "amount": str(payment.amount),
                "method": payment.method,
                "kind": payment.kind,
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
@api_role_required(*FRONT_DESK_MONEY)
@require_POST
def reservation_refund(request, pk):
    reservation = _get_reservation(request, pk)
    if reservation is None:
        return json_error("Reservation not found.", status=404)
    data = parse_json(request)
    amount = data.get("amount")
    fee = None
    if amount not in (None, ""):
        try:
            fee = Decimal(str(amount).replace(",", "."))
        except (InvalidOperation, TypeError, ValueError):
            return json_error("Invalid amount.")
    method = (data.get("method") or "cash").strip().lower()
    if method not in ("cash", "card", "transfer"):
        return json_error("method must be cash, card, or transfer.")
    try:
        from folio.services import ensure_folio_for_reservation, refund_overpayment

        folio = ensure_folio_for_reservation(reservation, allow_pre_checkin=True)
        payment = refund_overpayment(
            folio,
            request.user,
            amount=fee,
            method=method,
            note=(data.get("note") or "").strip(),
        )
        folio.refresh_from_db()
        return json_ok(
            {
                "payment_id": payment.pk,
                "amount": str(payment.amount),
                "method": payment.method,
                "kind": payment.kind,
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
@api_role_required(*INVENTORY)
@require_GET
def minibar_items(request):
    from inventory.models import StockItem

    hotel = getattr(request, "active_property", None)
    qs = StockItem.objects.filter(
        tenant=request.tenant, is_active=True, is_minibar=True
    )
    if hotel is not None:
        qs = qs.filter(Q(hotel=hotel) | Q(hotel__isnull=True))
    return json_ok(
        {
            "items": [
                {
                    "id": i.pk,
                    "name": i.name,
                    "sku": getattr(i, "sku", "") or "",
                    "sell_price": str(i.sell_price),
                    "quantity_on_hand": str(i.quantity_on_hand),
                }
                for i in qs.order_by("name")[:200]
            ]
        }
    )


@api_login_required
@api_role_required(*INVENTORY)
@require_POST
def reservation_minibar(request, pk):
    reservation = _get_reservation(request, pk)
    if reservation is None:
        return json_error("Reservation not found.", status=404)
    data = parse_json(request)
    item_id = data.get("item_id")
    if not item_id:
        return json_error("item_id required.")
    try:
        quantity = Decimal(str(data.get("quantity") or "1").replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return json_error("Invalid quantity.")
    if quantity <= 0:
        return json_error("quantity must be positive.")

    from inventory.models import StockItem
    from inventory.services import sell_minibar

    item = StockItem.objects.filter(
        pk=item_id, tenant=request.tenant, is_active=True, is_minibar=True
    ).first()
    if item is None:
        return json_error("Minibar item not found.", status=404)
    try:
        sale = sell_minibar(
            reservation=reservation,
            item=item,
            user=request.user,
            quantity=quantity,
        )
        balance = None
        try:
            balance = str(reservation.folio.balance)
        except Exception:
            pass
        return json_ok(
            {
                "sale_id": sale.pk,
                "item": item.name,
                "quantity": str(sale.quantity),
                "amount": str(sale.quantity * sale.unit_price),
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
@api_role_required(*FRONT_OFFICE)
@require_POST
def reservation_confirm(request, pk):
    reservation = _get_reservation(request, pk)
    if reservation is None:
        return json_error("Reservation not found.", status=404)
    data = parse_json(request)
    try:
        confirm_inquiry(
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
def reservation_amend(request, pk):
    """Amend dates / adults / children / nightly_rate (shared apply_amendment)."""
    reservation = _get_reservation(request, pk)
    if reservation is None:
        return json_error("Reservation not found.", status=404)
    data = parse_json(request)
    try:
        check_in = reservation.check_in
        check_out = reservation.check_out
        if data.get("check_in"):
            check_in = date.fromisoformat(str(data["check_in"]).strip())
        if data.get("check_out"):
            check_out = date.fromisoformat(str(data["check_out"]).strip())
        adults = int(data["adults"]) if "adults" in data else reservation.adults
        children = int(data["children"]) if "children" in data else reservation.children
    except (TypeError, ValueError):
        return json_error("Invalid dates or guest counts.")

    payload = {
        "check_in": check_in,
        "check_out": check_out,
        "room": reservation.room,
        "rate_plan": reservation.rate_plan,
        "nightly_rate": reservation.nightly_rate,
        "adults": max(1, adults),
        "children": max(0, children),
        "reason": (data.get("reason") or "amend").strip() or "amend",
    }
    if "nightly_rate" in data and data.get("nightly_rate") not in (None, ""):
        try:
            payload["nightly_rate"] = Decimal(
                str(data["nightly_rate"]).replace(",", ".")
            )
        except (InvalidOperation, TypeError, ValueError):
            return json_error("Invalid nightly_rate.")
    try:
        apply_amendment(reservation, request.user, payload)
        reservation.refresh_from_db()
        return json_ok(_reservation_summary(reservation))
    except ValidationError as exc:
        return json_error(
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
            status=400,
        )


@api_login_required
@api_role_required(*CASH)
@require_POST
def cash_shift_movement(request):
    from folio.models import CashShiftMovement
    from folio.services import add_cash_movement, get_open_shift

    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    shift = get_open_shift(request.tenant, hotel=hotel)
    if shift is None:
        return json_error("No open cash shift.", status=400)
    data = parse_json(request)
    kind = (data.get("kind") or "").strip()
    if kind not in dict(CashShiftMovement.Kind.choices):
        return json_error("kind must be pay_in or pay_out.")
    try:
        amount = Decimal(str(data.get("amount", "")).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return json_error("Valid amount required.")
    try:
        movement = add_cash_movement(
            shift,
            request.user,
            kind=kind,
            amount=amount,
            note=(data.get("note") or "").strip(),
        )
        return json_ok(
            {
                "movement_id": movement.pk,
                "kind": movement.kind,
                "amount": str(movement.amount),
            },
            status=201,
        )
    except ValidationError as exc:
        return json_error(
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
            status=400,
        )


@api_login_required
@api_role_required(*FRONT_OFFICE)
@require_GET
def guest_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = Guest.objects.filter(tenant=request.tenant)
    if q:
        qs = qs.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(phone__icontains=q)
            | Q(email__icontains=q)
        )
    items = [
        {
            "id": g.pk,
            "name": str(g),
            "first_name": g.first_name,
            "last_name": g.last_name,
            "phone": g.phone,
            "email": g.email,
            "is_vip": g.is_vip,
            "is_blacklisted": g.is_blacklisted,
        }
        for g in qs.order_by("first_name", "last_name")[:100]
    ]
    return json_ok({"q": q, "items": items})


@api_login_required
@api_role_required(*FRONT_OFFICE)
@require_GET
def guest_detail(request, pk):
    guest = Guest.objects.filter(pk=pk, tenant=request.tenant).first()
    if guest is None:
        return json_error("Guest not found.", status=404)
    docs = [
        {
            "id": d.pk,
            "doc_type": d.doc_type,
            "number": d.number,
            "issued_country": d.issued_country,
            "expiry_date": d.expiry_date.isoformat() if d.expiry_date else None,
        }
        for d in guest.documents.all()[:20]
    ]
    stays = [
        _reservation_summary(r)
        for r in Reservation.objects.filter(tenant=request.tenant, guest=guest)
        .select_related("guest", "room", "hotel")
        .order_by("-check_in")[:20]
    ]
    return json_ok(
        {
            "id": guest.pk,
            "first_name": guest.first_name,
            "last_name": guest.last_name,
            "name": str(guest),
            "phone": guest.phone,
            "email": guest.email,
            "nationality": guest.nationality,
            "is_vip": guest.is_vip,
            "is_blacklisted": guest.is_blacklisted,
            "notes": guest.notes or "",
            "documents": docs,
            "stays": stays,
        }
    )


@api_login_required
@api_role_required(*FRONT_OFFICE)
@require_POST
def guest_create(request):
    data = parse_json(request)
    first_name = (data.get("first_name") or "").strip()
    if not first_name:
        return json_error("first_name required.")
    guest = Guest.objects.create(
        tenant=request.tenant,
        first_name=first_name,
        last_name=(data.get("last_name") or "").strip(),
        phone=(data.get("phone") or "").strip(),
        email=(data.get("email") or "").strip(),
        nationality=(data.get("nationality") or "").strip(),
        notes=(data.get("notes") or "").strip(),
        is_vip=bool(data.get("is_vip")),
    )
    return json_ok(
        {
            "id": guest.pk,
            "name": str(guest),
            "first_name": guest.first_name,
            "last_name": guest.last_name,
            "phone": guest.phone,
        },
        status=201,
    )


@api_login_required
@api_role_required(*ROOM_STATUS_ROLES)
@require_GET
def housekeeping_board(request):
    hotel = getattr(request, "active_property", None)
    rooms = Room.objects.filter(tenant=request.tenant, is_active=True).select_related(
        "room_type"
    )
    if hotel is not None:
        rooms = rooms.filter(property=hotel)
    from housekeeping.models import HousekeepingTask

    tasks = HousekeepingTask.objects.filter(
        tenant=request.tenant,
        status__in=[
            HousekeepingTask.Status.PENDING,
            HousekeepingTask.Status.IN_PROGRESS,
        ],
    ).select_related("room", "assigned_to")
    if hotel is not None:
        tasks = tasks.filter(room__property=hotel)

    room_rows = []
    stats = {"ready": 0, "dirty": 0, "cleaning": 0, "ooo": 0, "total": 0}
    for room in rooms.order_by("number"):
        stats["total"] += 1
        if room.status == Room.Status.READY:
            stats["ready"] += 1
        elif room.status == Room.Status.DIRTY:
            stats["dirty"] += 1
        elif room.status in (Room.Status.CLEANING, Room.Status.INSPECTED):
            stats["cleaning"] += 1
        elif room.status == Room.Status.OUT_OF_ORDER:
            stats["ooo"] += 1
        room_rows.append(
            {
                "id": room.pk,
                "number": room.number,
                "status": room.status,
                "room_type": room.room_type.name if room.room_type_id else "",
            }
        )
    task_rows = [
        {
            "id": t.pk,
            "title": t.title,
            "status": t.status,
            "room": {"id": t.room_id, "number": t.room.number},
            "assigned_to": t.assigned_to.get_username() if t.assigned_to_id else "",
        }
        for t in tasks.order_by("-created_at")[:100]
    ]
    return json_ok({"stats": stats, "rooms": room_rows, "tasks": task_rows})


@api_login_required
@api_role_required(*HOUSEKEEPING, TenantMembership.Role.RECEPTIONIST, TenantMembership.Role.MANAGER)
@require_POST
def housekeeping_complete(request, pk):
    from housekeeping.models import HousekeepingTask
    from housekeeping.services import complete_task

    hotel = getattr(request, "active_property", None)
    qs = HousekeepingTask.objects.filter(pk=pk, tenant=request.tenant)
    if hotel is not None:
        qs = qs.filter(room__property=hotel)
    task = qs.select_related("room").first()
    if task is None:
        return json_error("Task not found.", status=404)
    try:
        complete_task(task, user=request.user)
        task.refresh_from_db()
        return json_ok(
            {
                "task_id": task.pk,
                "status": task.status,
                "room": {"id": task.room_id, "number": task.room.number, "status": task.room.status},
            }
        )
    except ValidationError as exc:
        return json_error(
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
            status=400,
        )


@api_login_required
@api_role_required(*FLOOR_VIEW)
@require_GET
def inquiries(request):
    qs = (
        Reservation.objects.filter(
            tenant=request.tenant, status=Reservation.Status.INQUIRY
        )
        .select_related("guest", "room", "hotel")
        .order_by("check_in", "code")
    )
    hotel = getattr(request, "active_property", None)
    if hotel is not None:
        qs = qs.filter(hotel=hotel)
    return json_ok({"items": [_reservation_summary(r) for r in qs[:100]]})


def _jsonable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


@api_login_required
@api_role_required(*MONEY_VOID)
@require_POST
def void_charge(request, pk):
    from folio.models import FolioCharge
    from folio.services import void_charge as do_void

    data = parse_json(request)
    charge = FolioCharge.objects.filter(
        pk=pk, tenant=request.tenant, is_void=False
    ).select_related("folio__reservation").first()
    if charge is None:
        return json_error("Charge not found.", status=404)
    hotel = getattr(request, "active_property", None)
    res = getattr(charge.folio, "reservation", None)
    if hotel is not None and res is not None and res.hotel_id != hotel.pk:
        return json_error("Charge belongs to another hotel.", status=400)
    try:
        do_void(charge, request.user, reason=(data.get("reason") or "").strip())
        charge.refresh_from_db()
        balance = str(charge.folio.balance)
        return json_ok(
            {
                "charge_id": charge.pk,
                "is_void": charge.is_void,
                "balance": balance,
            }
        )
    except ValidationError as exc:
        return json_error(
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
            status=400,
        )


@api_login_required
@api_role_required(*MONEY_VOID)
@require_POST
def void_payment(request, pk):
    from folio.models import GuestPayment
    from folio.services import void_payment as do_void

    data = parse_json(request)
    payment = GuestPayment.objects.filter(
        pk=pk, tenant=request.tenant, is_void=False
    ).select_related("folio__reservation").first()
    if payment is None:
        return json_error("Payment not found.", status=404)
    hotel = getattr(request, "active_property", None)
    res = getattr(payment.folio, "reservation", None)
    if hotel is not None and res is not None and res.hotel_id != hotel.pk:
        return json_error("Payment belongs to another hotel.", status=400)
    try:
        do_void(payment, request.user, reason=(data.get("reason") or "").strip())
        payment.refresh_from_db()
        return json_ok(
            {
                "payment_id": payment.pk,
                "is_void": payment.is_void,
                "balance": str(payment.folio.balance),
            }
        )
    except ValidationError as exc:
        return json_error(
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
            status=400,
        )


@api_login_required
@api_role_required(*FLOOR_VIEW)
@require_GET
def calendar(request):
    from bookings.timeline import build_room_timeline, mark_covers_today
    from django.utils import timezone

    today = timezone.localdate()
    start_s = (request.GET.get("start") or "").strip()
    try:
        start = date.fromisoformat(start_s) if start_s else today
    except ValueError:
        return json_error("Invalid start date.")
    try:
        days_count = min(31, max(7, int(request.GET.get("days") or 14)))
    except (TypeError, ValueError):
        days_count = 14

    hotel = getattr(request, "active_property", None)
    timeline = build_room_timeline(
        request.tenant, hotel, start, days_count=days_count
    )
    mark_covers_today(timeline, today)

    rows = []
    for row in timeline["rows"]:
        room = row["room"]
        segments = []
        for seg in row["segments"]:
            if seg["kind"] == "empty":
                segments.append(
                    {
                        "kind": "empty",
                        "date": seg["date"].isoformat(),
                        "colspan": seg["colspan"],
                    }
                )
            else:
                res = seg["reservation"]
                folio = seg.get("folio")
                segments.append(
                    {
                        "kind": "stay",
                        "colspan": seg["colspan"],
                        "status": seg["status"],
                        "is_vip": seg["is_vip"],
                        "covers_today": seg.get("covers_today", False),
                        "start_day": seg["start_day"].isoformat(),
                        "reservation": {
                            "id": res.pk,
                            "code": res.code,
                            "guest": str(res.guest) if res.guest_id else "",
                            "check_in": res.check_in.isoformat(),
                            "check_out": res.check_out.isoformat(),
                        },
                        "balance": str(folio.balance) if folio else None,
                    }
                )
        rows.append(
            {
                "room": {
                    "id": room.pk,
                    "number": room.number,
                    "status": room.status,
                    "room_type": room.room_type.name if room.room_type_id else "",
                },
                "segments": segments,
            }
        )

    return json_ok(
        {
            "start": timeline["start"].isoformat(),
            "end": timeline["end"].isoformat(),
            "days": [d.isoformat() for d in timeline["days"]],
            "days_count": timeline["days_count"],
            "stats": timeline["stats"],
            "rows": rows,
        }
    )


@api_login_required
@api_role_required(*DASHBOARD)
@require_GET
def flash_report(request):
    from django.utils import timezone
    from reports.accounting import build_daily_flash
    from reports.operations import operations_kpis

    day = timezone.localdate()
    day_s = (request.GET.get("date") or "").strip()
    if day_s:
        try:
            day = date.fromisoformat(day_s)
        except ValueError:
            return json_error("Invalid date.")
    hotel = getattr(request, "active_property", None)
    flash = build_daily_flash(request.tenant, day, hotel=hotel)
    kpis = operations_kpis(request.tenant, day, hotel=hotel)
    return json_ok(
        {
            "day": day.isoformat(),
            "flash": _jsonable(flash),
            "kpis": _jsonable(kpis),
        }
    )


@api_login_required
@api_role_required(*FLOOR_VIEW)
@require_GET
def maintenance_list(request):
    from maintenance.models import MaintenanceTicket

    hotel = getattr(request, "active_property", None)
    qs = MaintenanceTicket.objects.filter(tenant=request.tenant).select_related(
        "room", "assignee"
    )
    if hotel is not None:
        qs = qs.filter(Q(room__property=hotel) | Q(room__isnull=True))
    status = (request.GET.get("status") or "").strip()
    if status:
        qs = qs.filter(status=status)
    else:
        qs = qs.filter(
            status__in=[
                MaintenanceTicket.Status.OPEN,
                MaintenanceTicket.Status.IN_PROGRESS,
            ]
        )
    items = [
        {
            "id": t.pk,
            "title": t.title,
            "description": t.description or "",
            "priority": t.priority,
            "status": t.status,
            "set_room_ooo": t.set_room_ooo,
            "room": (
                {"id": t.room_id, "number": t.room.number}
                if t.room_id
                else None
            ),
            "assignee": t.assignee.get_username() if t.assignee_id else "",
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in qs.order_by("-created_at")[:100]
    ]
    return json_ok({"items": items})


@api_login_required
@api_role_required(*OPS_MANAGER, TenantMembership.Role.MANAGER, TenantMembership.Role.RECEPTIONIST)
@require_POST
def maintenance_create(request):
    from maintenance.models import MaintenanceTicket
    from maintenance.services import open_ticket

    data = parse_json(request)
    title = (data.get("title") or "").strip()
    if not title:
        return json_error("title required.")
    hotel = getattr(request, "active_property", None)
    room = None
    room_id = data.get("room_id")
    if room_id:
        qs = Room.objects.filter(pk=room_id, tenant=request.tenant, is_active=True)
        if hotel is not None:
            qs = qs.filter(property=hotel)
        room = qs.first()
        if room is None:
            return json_error("Room not found.", status=404)
    priority = (data.get("priority") or MaintenanceTicket.Priority.MEDIUM).strip()
    if priority not in dict(MaintenanceTicket.Priority.choices):
        return json_error("Invalid priority.")
    ticket = MaintenanceTicket(
        tenant=request.tenant,
        room=room,
        title=title,
        description=(data.get("description") or "").strip(),
        priority=priority,
        set_room_ooo=bool(data.get("set_room_ooo")),
        created_by=request.user,
    )
    ticket.save()
    open_ticket(ticket)
    ticket.refresh_from_db()
    return json_ok(
        {
            "id": ticket.pk,
            "title": ticket.title,
            "status": ticket.status,
            "room": (
                {"id": ticket.room_id, "number": ticket.room.number}
                if ticket.room_id
                else None
            ),
        },
        status=201,
    )


@api_login_required
@api_role_required(*OPS_MANAGER, TenantMembership.Role.MANAGER, TenantMembership.Role.RECEPTIONIST)
@require_POST
def maintenance_complete(request, pk):
    from maintenance.models import MaintenanceTicket
    from maintenance.services import complete_ticket

    hotel = getattr(request, "active_property", None)
    qs = MaintenanceTicket.objects.filter(pk=pk, tenant=request.tenant)
    if hotel is not None:
        qs = qs.filter(Q(room__property=hotel) | Q(room__isnull=True))
    ticket = qs.select_related("room").first()
    if ticket is None:
        return json_error("Ticket not found.", status=404)
    try:
        complete_ticket(ticket, user=request.user)
        ticket.refresh_from_db()
        return json_ok({"id": ticket.pk, "status": ticket.status})
    except ValidationError as exc:
        return json_error(
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
            status=400,
        )
