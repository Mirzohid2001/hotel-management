"""Web-parity API endpoints — guest edit, folio ops, companies, ledger, groups, audit, expenses."""

from datetime import date
from decimal import Decimal, InvalidOperation
import base64

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from bookings.models import Reservation, ReservationGroup
from bookings.services import create_group_booking
from core.roles import (
    ACCOUNTING,
    AUDIT,
    FINANCE,
    FLOOR_VIEW,
    FRONT_DESK_MONEY,
    FRONT_OFFICE,
    STAY_DESK,
)
from guests.models import Company, Guest, GuestDocument
from properties.models import Room, RoomType
from tenants.models import TenantMembership

from .auth import api_login_required, api_role_required, json_error, json_ok, parse_json
from .views import _get_reservation, _reservation_summary


def _err(exc):
    return json_error(
        "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
        status=400,
    )


def _company_row(c: Company) -> dict:
    return {
        "id": c.pk,
        "name": c.name,
        "inn": c.inn or "",
        "phone": c.phone or "",
        "email": c.email or "",
        "address": c.address or "",
        "is_active": c.is_active,
        "payment_terms_days": c.payment_terms_days,
        "credit_limit": str(c.credit_limit),
    }


def _guest_payload(guest: Guest) -> dict:
    docs = [
        {
            "id": d.pk,
            "doc_type": d.doc_type,
            "number": d.number,
            "issued_country": d.issued_country,
            "expiry_date": d.expiry_date.isoformat() if d.expiry_date else None,
        }
        for d in guest.documents.all()[:30]
    ]
    stays = [
        _reservation_summary(r)
        for r in Reservation.objects.filter(tenant=guest.tenant, guest=guest)
        .select_related("guest", "room", "hotel")
        .order_by("-check_in")[:30]
    ]
    company_name = ""
    if guest.company_id:
        company_name = guest.company.name if guest.company_id else ""
    return {
        "id": guest.pk,
        "first_name": guest.first_name,
        "last_name": guest.last_name,
        "name": str(guest),
        "phone": guest.phone,
        "email": guest.email,
        "nationality": guest.nationality,
        "is_vip": guest.is_vip,
        "is_blacklisted": guest.is_blacklisted,
        "blacklist_reason": guest.blacklist_reason or "",
        "notes": guest.notes or "",
        "company_id": guest.company_id,
        "company": company_name,
        "documents": docs,
        "stays": stays,
    }


@api_login_required
@api_role_required(*FRONT_OFFICE)
@require_http_methods(["GET", "POST"])
def guest_update(request, pk):
    guest = (
        Guest.objects.filter(pk=pk, tenant=request.tenant)
        .select_related("company")
        .prefetch_related("documents")
        .first()
    )
    if guest is None:
        return json_error("Guest not found.", status=404)
    if request.method == "GET":
        return json_ok(_guest_payload(guest))
    data = parse_json(request)
    for field in ("first_name", "last_name", "phone", "email", "nationality", "notes"):
        if field in data:
            setattr(guest, field, (data.get(field) or "").strip())
    if "is_vip" in data:
        guest.is_vip = bool(data["is_vip"])
    if "is_blacklisted" in data:
        guest.is_blacklisted = bool(data["is_blacklisted"])
        guest.blacklist_reason = (data.get("blacklist_reason") or "").strip()
    if "company_id" in data:
        cid = data.get("company_id")
        if cid in (None, "", 0, "0"):
            guest.company = None
        else:
            company = Company.objects.filter(pk=cid, tenant=request.tenant).first()
            if company is None:
                return json_error("Company not found.", status=404)
            guest.company = company
    if not guest.first_name.strip():
        return json_error("first_name required.")
    guest.save()
    return json_ok(_guest_payload(guest))


@api_login_required
@api_role_required(*FRONT_OFFICE)
@require_POST
def guest_add_document(request, pk):
    guest = Guest.objects.filter(pk=pk, tenant=request.tenant).first()
    if guest is None:
        return json_error("Guest not found.", status=404)
    data = parse_json(request)
    number = (data.get("number") or "").strip()
    if not number:
        return json_error("number required.")
    doc_type = (data.get("doc_type") or GuestDocument.DocType.PASSPORT).strip()
    if doc_type not in dict(GuestDocument.DocType.choices):
        return json_error("Invalid doc_type.")
    expiry = None
    if data.get("expiry_date"):
        try:
            expiry = date.fromisoformat(str(data["expiry_date"]).strip())
        except ValueError:
            return json_error("Invalid expiry_date.")
    doc = GuestDocument.objects.create(
        tenant=request.tenant,
        guest=guest,
        doc_type=doc_type,
        number=number,
        issued_country=(data.get("issued_country") or "").strip(),
        expiry_date=expiry,
    )
    return json_ok(
        {
            "id": doc.pk,
            "doc_type": doc.doc_type,
            "number": doc.number,
            "issued_country": doc.issued_country,
            "expiry_date": doc.expiry_date.isoformat() if doc.expiry_date else None,
        },
        status=201,
    )


@api_login_required
@api_role_required(*FRONT_DESK_MONEY)
@require_GET
def folio_receipt(request, pk):
    """On-screen receipt + optional PDF (base64)."""
    from folio.models import Folio, FolioCharge, GuestPayment
    from folio.pdf import build_folio_pdf

    folio = (
        Folio.objects.filter(pk=pk, tenant=request.tenant)
        .select_related(
            "reservation", "reservation__guest", "reservation__room", "reservation__hotel"
        )
        .first()
    )
    if folio is None:
        return json_error("Folio not found.", status=404)
    hotel = getattr(request, "active_property", None)
    res = folio.reservation
    if hotel is not None and res is not None and res.hotel_id != hotel.pk:
        return json_error("Folio belongs to another hotel.", status=400)

    charges = [
        {
            "id": c.pk,
            "description": c.description,
            "amount": str(c.amount),
            "charge_type": c.charge_type,
        }
        for c in folio.charges.filter(is_void=False).order_by("created_at")
    ]
    payments = [
        {
            "id": p.pk,
            "amount": str(p.amount),
            "method": p.method,
            "kind": p.kind,
            "note": p.note or "",
        }
        for p in folio.payments.filter(is_void=False).order_by("created_at")
    ]
    pdf_b64 = None
    if (request.GET.get("pdf") or "").strip() in ("1", "true", "yes"):
        pdf_b64 = base64.b64encode(build_folio_pdf(folio)).decode("ascii")

    return json_ok(
        {
            "folio_id": folio.pk,
            "balance": str(folio.balance),
            "is_open": folio.is_open,
            "reservation": _reservation_summary(res) if res else None,
            "charges": charges,
            "payments": payments,
            "pdf_base64": pdf_b64,
            "filename": f"invoice-{res.code if res else folio.pk}.pdf",
        }
    )


@api_login_required
@api_role_required(*FRONT_DESK_MONEY)
@require_POST
def folio_close(request, pk):
    from folio.models import Folio
    from folio.services import close_folio

    folio = Folio.objects.filter(pk=pk, tenant=request.tenant).select_related(
        "reservation"
    ).first()
    if folio is None:
        return json_error("Folio not found.", status=404)
    try:
        close_folio(folio)
        folio.refresh_from_db()
        return json_ok({"folio_id": folio.pk, "is_open": folio.is_open})
    except ValidationError as exc:
        return _err(exc)


@api_login_required
@api_role_required(*FRONT_DESK_MONEY)
@require_POST
def folio_split_pay(request, pk):
    from folio.models import Folio, GuestPayment
    from folio.services import add_split_payments

    folio = Folio.objects.filter(pk=pk, tenant=request.tenant).first()
    if folio is None:
        return json_error("Folio not found.", status=404)
    data = parse_json(request)
    raw_lines = data.get("lines") or []
    if not isinstance(raw_lines, list):
        return json_error("lines must be a list.")
    lines = []
    for row in raw_lines:
        try:
            amount = Decimal(str(row.get("amount", "")).replace(",", "."))
        except (InvalidOperation, TypeError, ValueError):
            continue
        method = (row.get("method") or "cash").strip().lower()
        kind = (row.get("kind") or GuestPayment.Kind.PAYMENT).strip()
        lines.append(
            {
                "amount": amount,
                "method": method,
                "kind": kind,
                "note": (row.get("note") or "").strip(),
            }
        )
    try:
        created = add_split_payments(folio, request.user, lines)
        folio.refresh_from_db()
        return json_ok(
            {
                "payments": [
                    {"id": p.pk, "amount": str(p.amount), "method": p.method}
                    for p in created
                ],
                "balance": str(folio.balance),
            },
            status=201,
        )
    except ValidationError as exc:
        return _err(exc)


@api_login_required
@api_role_required(*FRONT_DESK_MONEY)
@require_POST
def reservation_emehmon(request, pk):
    from folio.services import collect_emehmon_fee

    reservation = _get_reservation(request, pk)
    if reservation is None:
        return json_error("Reservation not found.", status=404)
    data = parse_json(request)
    method = (data.get("method") or "cash").strip().lower()
    amount = None
    if data.get("amount") not in (None, ""):
        try:
            amount = Decimal(str(data["amount"]).replace(",", "."))
        except (InvalidOperation, TypeError, ValueError):
            return json_error("Invalid amount.")
    try:
        charge, payment = collect_emehmon_fee(
            reservation,
            request.user,
            amount=amount,
            method=method,
            note=(data.get("note") or "").strip(),
        )
        return json_ok(
            {
                "charge_id": charge.pk,
                "payment_id": payment.pk,
                "amount": str(payment.amount),
                "balance": str(charge.folio.balance),
            },
            status=201,
        )
    except ValidationError as exc:
        return _err(exc)


@api_login_required
@api_role_required(*FINANCE, TenantMembership.Role.RECEPTIONIST, TenantMembership.Role.MANAGER)
@require_POST
def folio_to_company(request, pk):
    from folio.city_ledger import transfer_open_charges_to_company
    from folio.models import Folio

    folio = (
        Folio.objects.filter(pk=pk, tenant=request.tenant)
        .select_related("reservation", "reservation__company", "reservation__guest")
        .first()
    )
    if folio is None:
        return json_error("Folio not found.", status=404)
    data = parse_json(request)
    company = None
    if data.get("company_id"):
        company = Company.objects.filter(
            pk=data["company_id"], tenant=request.tenant, is_active=True
        ).first()
        if company is None:
            return json_error("Company not found.", status=404)
    try:
        invoice = transfer_open_charges_to_company(
            folio,
            request.user,
            company=company,
            notes=(data.get("notes") or "").strip(),
        )
        return json_ok(
            {
                "invoice_id": invoice.pk,
                "code": invoice.code,
                "status": invoice.status,
                "total": str(invoice.lines_total),
                "balance": str(invoice.balance),
                "company": invoice.company.name if invoice.company_id else "",
            },
            status=201,
        )
    except ValidationError as exc:
        return _err(exc)


@api_login_required
@api_role_required(*FRONT_OFFICE, *FINANCE, TenantMembership.Role.MANAGER)
@require_GET
def companies(request):
    qs = Company.objects.filter(tenant=request.tenant)
    if (request.GET.get("active") or "1") == "1":
        qs = qs.filter(is_active=True)
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(inn__icontains=q) | Q(phone__icontains=q))
    return json_ok({"items": [_company_row(c) for c in qs.order_by("name")[:100]]})


@api_login_required
@api_role_required(*FRONT_OFFICE, *FINANCE, TenantMembership.Role.MANAGER)
@require_POST
def company_create(request):
    data = parse_json(request)
    name = (data.get("name") or "").strip()
    if not name:
        return json_error("name required.")
    if Company.objects.filter(tenant=request.tenant, name__iexact=name).exists():
        return json_error("Company with this name already exists.")
    company = Company.objects.create(
        tenant=request.tenant,
        name=name,
        inn=(data.get("inn") or "").strip(),
        phone=(data.get("phone") or "").strip(),
        email=(data.get("email") or "").strip(),
        address=(data.get("address") or "").strip(),
        notes=(data.get("notes") or "").strip(),
    )
    return json_ok(_company_row(company), status=201)


@api_login_required
@api_role_required(*FINANCE, TenantMembership.Role.MANAGER, TenantMembership.Role.RECEPTIONIST)
@require_GET
def city_ledger(request):
    from folio.models import CompanyInvoice

    qs = CompanyInvoice.objects.filter(tenant=request.tenant).select_related("company")
    hotel = getattr(request, "active_property", None)
    if hotel is not None:
        qs = qs.filter(Q(hotel=hotel) | Q(hotel__isnull=True))
    status = (request.GET.get("status") or "open").strip()
    if status == "open":
        qs = qs.filter(
            status__in=[CompanyInvoice.Status.OPEN, CompanyInvoice.Status.PARTIAL]
        )
    elif status and status != "all":
        qs = qs.filter(status=status)
    items = [
        {
            "id": inv.pk,
            "code": inv.code,
            "status": inv.status,
            "company": inv.company.name if inv.company_id else "",
            "company_id": inv.company_id,
            "total": str(inv.lines_total),
            "balance": str(inv.balance),
            "issued_at": inv.issued_at.isoformat() if inv.issued_at else None,
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
        }
        for inv in qs.order_by("-issued_at", "-id")[:100]
    ]
    return json_ok({"items": items})


@api_login_required
@api_role_required(*FINANCE)
@require_POST
def city_ledger_pay(request, pk):
    from folio.city_ledger import add_company_payment
    from folio.models import CompanyInvoice

    invoice = CompanyInvoice.objects.filter(pk=pk, tenant=request.tenant).first()
    if invoice is None:
        return json_error("Invoice not found.", status=404)
    data = parse_json(request)
    try:
        amount = Decimal(str(data.get("amount", "")).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return json_error("Valid amount required.")
    method = (data.get("method") or "transfer").strip().lower()
    try:
        pay = add_company_payment(
            invoice,
            request.user,
            amount=amount,
            method=method,
            note=(data.get("note") or "").strip(),
        )
        invoice.refresh_from_db()
        return json_ok(
            {
                "payment_id": pay.pk,
                "amount": str(pay.amount),
                "invoice_status": invoice.status,
                "balance": str(invoice.balance),
            },
            status=201,
        )
    except ValidationError as exc:
        return _err(exc)


@api_login_required
@api_role_required(*FLOOR_VIEW)
@require_GET
def groups(request):
    qs = ReservationGroup.objects.filter(tenant=request.tenant).select_related(
        "hotel", "company"
    )
    hotel = getattr(request, "active_property", None)
    if hotel is not None:
        qs = qs.filter(hotel=hotel)
    items = [
        {
            "id": g.pk,
            "code": g.code,
            "name": g.name,
            "check_in": g.check_in.isoformat(),
            "check_out": g.check_out.isoformat(),
            "company": g.company.name if g.company_id else "",
            "hotel": g.hotel.name if g.hotel_id else "",
            "rooms": g.reservations.count(),
        }
        for g in qs.order_by("-check_in")[:50]
    ]
    return json_ok({"items": items})


@api_login_required
@api_role_required(*FLOOR_VIEW)
@require_GET
def group_detail(request, pk):
    group = (
        ReservationGroup.objects.filter(pk=pk, tenant=request.tenant)
        .select_related("hotel", "company")
        .first()
    )
    if group is None:
        return json_error("Group not found.", status=404)
    rooms = [
        _reservation_summary(r)
        for r in group.reservations.select_related("guest", "room", "hotel").order_by(
            "code"
        )
    ]
    return json_ok(
        {
            "id": group.pk,
            "code": group.code,
            "name": group.name,
            "check_in": group.check_in.isoformat(),
            "check_out": group.check_out.isoformat(),
            "company": group.company.name if group.company_id else "",
            "notes": group.notes or "",
            "reservations": rooms,
        }
    )


@api_login_required
@api_role_required(*FRONT_OFFICE)
@require_POST
def group_create(request):
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    data = parse_json(request)
    name = (data.get("name") or "").strip()
    if not name:
        return json_error("name required.")
    try:
        check_in = date.fromisoformat(str(data.get("check_in") or "").strip())
        check_out = date.fromisoformat(str(data.get("check_out") or "").strip())
    except ValueError:
        return json_error("Invalid dates.")
    rooms_in = data.get("rooms") or []
    if not isinstance(rooms_in, list) or not rooms_in:
        return json_error("rooms required (list).")
    company = None
    if data.get("company_id"):
        company = Company.objects.filter(
            pk=data["company_id"], tenant=request.tenant
        ).first()
    rooms_data = []
    for row in rooms_in:
        first = (row.get("first_name") or "").strip()
        if not first:
            return json_error("Each room needs first_name.")
        guest = Guest.objects.create(
            tenant=request.tenant,
            first_name=first,
            last_name=(row.get("last_name") or "").strip(),
            phone=(row.get("phone") or "").strip(),
        )
        room = None
        room_type = None
        if row.get("room_id"):
            room = Room.objects.filter(
                pk=row["room_id"], tenant=request.tenant, property=hotel, is_active=True
            ).select_related("room_type").first()
            if room is None:
                return json_error(f"Room {row['room_id']} not found.", status=404)
            room_type = room.room_type
        elif row.get("room_type_id"):
            room_type = RoomType.objects.filter(
                pk=row["room_type_id"], tenant=request.tenant, property=hotel
            ).first()
            if room_type is None:
                return json_error("Room type not found.", status=404)
        else:
            return json_error("room_id or room_type_id required per room.")
        item = {
            "guest": guest,
            "room_type": room_type,
            "room": room,
            "adults": int(row.get("adults") or 1),
            "children": int(row.get("children") or 0),
        }
        if row.get("nightly_rate") not in (None, ""):
            try:
                item["nightly_rate"] = Decimal(str(row["nightly_rate"]).replace(",", "."))
            except (InvalidOperation, TypeError, ValueError):
                return json_error("Invalid nightly_rate.")
        rooms_data.append(item)
    try:
        group, created = create_group_booking(
            tenant=request.tenant,
            user=request.user,
            property_obj=hotel,
            name=name,
            check_in=check_in,
            check_out=check_out,
            rooms_data=rooms_data,
            company=company,
            notes=(data.get("notes") or "").strip(),
        )
        return json_ok(
            {
                "id": group.pk,
                "code": group.code,
                "name": group.name,
                "reservations": [_reservation_summary(r) for r in created],
            },
            status=201,
        )
    except ValidationError as exc:
        return _err(exc)


@api_login_required
@api_role_required(*AUDIT, TenantMembership.Role.MANAGER, TenantMembership.Role.RECEPTIONIST)
@require_GET
def night_audit_status(request):
    from django.utils import timezone
    from reports.models import NightAuditRun
    from reports.night_audit import audit_blockers, build_cod_checklist

    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    day = timezone.localdate()
    day_s = (request.GET.get("date") or "").strip()
    if day_s:
        try:
            day = date.fromisoformat(day_s)
        except ValueError:
            return json_error("Invalid date.")
    done = NightAuditRun.objects.filter(
        tenant=request.tenant, hotel=hotel, audit_date=day
    ).first()
    blockers = audit_blockers(request.tenant, day, hotel=hotel)
    checklist = build_cod_checklist(request.tenant, day, hotel=hotel)

    def _jsonable(v):
        if isinstance(v, Decimal):
            return str(v)
        if isinstance(v, date):
            return v.isoformat()
        if isinstance(v, dict):
            return {k: _jsonable(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [_jsonable(x) for x in v]
        return v

    return json_ok(
        {
            "day": day.isoformat(),
            "hotel": hotel.name,
            "already_run": done is not None,
            "run": (
                {
                    "id": done.pk,
                    "posted_room_charges": done.posted_room_charges,
                    "no_shows_marked": done.no_shows_marked,
                    "open_folios": done.open_folios,
                }
                if done
                else None
            ),
            "blockers": _jsonable(blockers),
            "checklist": _jsonable(checklist),
        }
    )


@api_login_required
@api_role_required(*AUDIT, TenantMembership.Role.MANAGER)
@require_POST
def night_audit_run(request):
    from django.utils import timezone
    from reports.night_audit import run_night_audit

    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    data = parse_json(request)
    day = timezone.localdate()
    if data.get("date"):
        try:
            day = date.fromisoformat(str(data["date"]).strip())
        except ValueError:
            return json_error("Invalid date.")
    try:
        run = run_night_audit(request.tenant, request.user, audit_date=day, hotel=hotel)
        return json_ok(
            {
                "id": run.pk,
                "day": run.audit_date.isoformat(),
                "posted_room_charges": run.posted_room_charges,
                "no_shows_marked": run.no_shows_marked,
                "open_folios": run.open_folios,
                "occupancy_percent": str(run.occupancy_percent),
                "revenue": str(run.revenue),
            },
            status=201,
        )
    except ValidationError as exc:
        return _err(exc)


@api_login_required
@api_role_required(*FINANCE, TenantMembership.Role.MANAGER)
@require_GET
def expenses(request):
    from finance.models import Expense

    qs = Expense.objects.filter(tenant=request.tenant).select_related(
        "category", "hotel", "vendor"
    )
    hotel = getattr(request, "active_property", None)
    if hotel is not None:
        qs = qs.filter(hotel=hotel)
    status = (request.GET.get("status") or "").strip()
    if status:
        qs = qs.filter(status=status)
    items = [
        {
            "id": e.pk,
            "title": e.title,
            "amount": str(e.amount),
            "status": e.status,
            "expense_date": e.expense_date.isoformat() if e.expense_date else None,
            "category": e.category.name if e.category_id else "",
            "funding": e.funding,
            "payment_method": e.payment_method,
        }
        for e in qs.order_by("-expense_date", "-id")[:100]
    ]
    return json_ok({"items": items})


@api_login_required
@api_role_required(*ACCOUNTING, TenantMembership.Role.MANAGER)
@require_GET
def pnl_report(request):
    from django.utils import timezone
    from reports.services import pnl_lite

    today = timezone.localdate()
    try:
        year = int(request.GET.get("year") or today.year)
        month = int(request.GET.get("month") or today.month)
    except (TypeError, ValueError):
        return json_error("Invalid year/month.")
    hotel = getattr(request, "active_property", None)
    data = pnl_lite(request.tenant, year, month, hotel=hotel)

    def _jsonable(v):
        if isinstance(v, Decimal):
            return str(v)
        if isinstance(v, date):
            return v.isoformat()
        if isinstance(v, dict):
            return {k: _jsonable(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [_jsonable(x) for x in v]
        return v

    return json_ok({"year": year, "month": month, "pnl": _jsonable(data)})
