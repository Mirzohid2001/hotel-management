"""Finance / setup parity endpoints — FX, expenses lifecycle, profit, city ledger detail."""

from __future__ import annotations

import base64
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from bookings.models import BookingReferrer
from core.roles import ACCOUNTING, FINANCE, FRONT_OFFICE, OPS_MANAGER
from guests.models import Company
from tenants.models import ExchangeRate, TenantMembership

from .auth import api_login_required, api_role_required, json_error, json_ok, parse_json
from .ops_extra import _referrer_row
from .parity import _company_row, _err, _expense_row


def _dec(raw, label="amount") -> Decimal:
    try:
        return Decimal(str(raw).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(f"Invalid {label}.") from exc


def _jsonable(v):
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if hasattr(v, "pk") and hasattr(v, "name"):
        return {"id": v.pk, "name": str(v.name)}
    return v


# ── FX ──────────────────────────────────────────────────────────────────────


@api_login_required
@api_role_required(*FINANCE, TenantMembership.Role.MANAGER)
@require_GET
def fx_list(request):
    from core.currency import get_rate_to_base

    qs = ExchangeRate.objects.filter(tenant=request.tenant).order_by(
        "-effective_on", "currency"
    )[:200]
    items = [
        {
            "id": r.pk,
            "currency": r.currency,
            "base_currency": r.base_currency,
            "rate": str(r.rate),
            "effective_on": r.effective_on.isoformat(),
            "note": r.note or "",
        }
        for r in qs
    ]
    live = {}
    for cur in ("USD", "EUR", "RUB"):
        try:
            live[cur] = str(get_rate_to_base(request.tenant, cur))
        except Exception:
            live[cur] = None
    return json_ok(
        {
            "items": items,
            "base_currency": getattr(request.tenant, "currency", None) or "UZS",
            "live": live,
        }
    )


@api_login_required
@api_role_required(*FINANCE, TenantMembership.Role.MANAGER)
@require_POST
def fx_create(request):
    data = parse_json(request)
    currency = (data.get("currency") or "").strip().upper()
    if not currency or len(currency) != 3:
        return json_error("currency (ISO 3) required.")
    base = (
        (data.get("base_currency") or getattr(request.tenant, "currency", None) or "UZS")
        .strip()
        .upper()
    )
    if currency == base:
        return json_error("currency must differ from base_currency.")
    try:
        rate = _dec(data.get("rate"), "rate")
        if rate <= 0:
            return json_error("rate must be positive.")
    except ValidationError as exc:
        return _err(exc)
    effective = timezone.localdate()
    if data.get("effective_on"):
        try:
            effective = date.fromisoformat(str(data["effective_on"]).strip())
        except ValueError:
            return json_error("Invalid effective_on.")
    row = ExchangeRate.objects.create(
        tenant=request.tenant,
        currency=currency,
        base_currency=base,
        rate=rate,
        effective_on=effective,
        note=(data.get("note") or "").strip(),
    )
    return json_ok(
        {
            "id": row.pk,
            "currency": row.currency,
            "base_currency": row.base_currency,
            "rate": str(row.rate),
            "effective_on": row.effective_on.isoformat(),
            "note": row.note or "",
        },
        status=201,
    )


@api_login_required
@api_role_required(*FINANCE, TenantMembership.Role.MANAGER)
@require_POST
def fx_delete(request, pk):
    row = ExchangeRate.objects.filter(pk=pk, tenant=request.tenant).first()
    if row is None:
        return json_error("Rate not found.", status=404)
    row.delete()
    return json_ok({"deleted": pk})


@api_login_required
@api_role_required(*FINANCE, TenantMembership.Role.MANAGER)
@require_POST
def fx_sync_cbu(request):
    from core.cbu import sync_cbu_rates_for_tenant

    data = parse_json(request)
    force = bool(data.get("force", True))
    try:
        result = sync_cbu_rates_for_tenant(request.tenant, force=force)
        return json_ok(_jsonable(result if result is not None else {"ok": True}))
    except Exception as exc:
        return json_error(str(exc), status=400)


# ── Expenses lifecycle extras ────────────────────────────────────────────────


def _expense_qs(request, pk):
    from finance.models import Expense

    hotel = getattr(request, "active_property", None)
    qs = Expense.objects.filter(pk=pk, tenant=request.tenant)
    if hotel is not None:
        qs = qs.filter(Q(hotel=hotel) | Q(hotel__isnull=True))
    return qs.select_related("category", "vendor")


@api_login_required
@api_role_required(*FINANCE, TenantMembership.Role.MANAGER)
@require_POST
def expense_reject(request, pk):
    from finance.services import reject_expense

    expense = _expense_qs(request, pk).first()
    if expense is None:
        return json_error("Expense not found.", status=404)
    data = parse_json(request)
    reason = (data.get("reason") or "").strip() or "Rad etildi"
    try:
        reject_expense(expense, request.user, reason=reason)
        expense.refresh_from_db()
        return json_ok(_expense_row(expense))
    except ValidationError as exc:
        return _err(exc)


@api_login_required
@api_role_required(*FINANCE, TenantMembership.Role.MANAGER)
@require_POST
def expense_reopen(request, pk):
    from finance.services import reopen_expense

    expense = _expense_qs(request, pk).first()
    if expense is None:
        return json_error("Expense not found.", status=404)
    try:
        reopen_expense(expense, request.user)
        expense.refresh_from_db()
        return json_ok(_expense_row(expense))
    except ValidationError as exc:
        return _err(exc)


@api_login_required
@api_role_required(*FINANCE, TenantMembership.Role.MANAGER)
@require_POST
def expense_delete(request, pk):
    from finance.services import delete_expense

    expense = _expense_qs(request, pk).first()
    if expense is None:
        return json_error("Expense not found.", status=404)
    try:
        delete_expense(expense, request.user)
        return json_ok({"deleted": pk})
    except ValidationError as exc:
        return _err(exc)


@api_login_required
@api_role_required(*FINANCE, TenantMembership.Role.MANAGER)
@require_POST
def expense_category_create(request):
    from finance.models import ExpenseCategory

    data = parse_json(request)
    name = (data.get("name") or "").strip()
    if not name:
        return json_error("name required.")
    cat = ExpenseCategory.objects.create(
        tenant=request.tenant, name=name, is_active=True
    )
    return json_ok({"id": cat.pk, "name": cat.name, "is_active": cat.is_active}, status=201)


@api_login_required
@api_role_required(*FINANCE, TenantMembership.Role.MANAGER)
@require_POST
def expense_vendor_create(request):
    from finance.models import Vendor

    data = parse_json(request)
    name = (data.get("name") or "").strip()
    if not name:
        return json_error("name required.")
    vendor = Vendor.objects.create(
        tenant=request.tenant,
        name=name,
        phone=(data.get("phone") or "").strip(),
        notes=(data.get("notes") or "").strip(),
        is_active=True,
    )
    return json_ok(
        {
            "id": vendor.pk,
            "name": vendor.name,
            "phone": vendor.phone or "",
            "is_active": vendor.is_active,
        },
        status=201,
    )


# ── Company / referrer update ────────────────────────────────────────────────


@api_login_required
@api_role_required(*FRONT_OFFICE, *FINANCE, TenantMembership.Role.MANAGER)
@require_http_methods(["GET", "POST", "PATCH"])
def company_update(request, pk):
    company = Company.objects.filter(pk=pk, tenant=request.tenant).first()
    if company is None:
        return json_error("Company not found.", status=404)
    if request.method == "GET":
        from folio.city_ledger import company_open_balance
        from folio.models import CompanyInvoice
        from bookings.models import Reservation
        from .views import _reservation_summary

        invoices = [
            {
                "id": inv.pk,
                "code": inv.code,
                "status": inv.status,
                "total": str(inv.lines_total),
                "balance": str(inv.balance),
                "issued_at": inv.issued_at.isoformat() if inv.issued_at else None,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
            }
            for inv in CompanyInvoice.objects.filter(
                tenant=request.tenant, company=company
            ).order_by("-issued_at")[:50]
        ]
        reservations = [
            _reservation_summary(r)
            for r in Reservation.objects.filter(
                tenant=request.tenant, company=company
            )
            .select_related("guest", "room", "hotel")
            .order_by("-check_in")[:40]
        ]
        row = _company_row(company)
        row["open_ar"] = str(company_open_balance(company))
        row["invoices"] = invoices
        row["reservations"] = reservations
        return json_ok(row)
    data = parse_json(request)
    for field in ("name", "inn", "phone", "email", "address", "notes"):
        if field in data:
            setattr(company, field, (data.get(field) or "").strip())
    if "is_active" in data:
        company.is_active = bool(data["is_active"])
    if "payment_terms_days" in data and data["payment_terms_days"] not in (None, ""):
        try:
            company.payment_terms_days = int(data["payment_terms_days"])
        except (TypeError, ValueError):
            return json_error("Invalid payment_terms_days.")
    if "credit_limit" in data and data["credit_limit"] not in (None, ""):
        try:
            company.credit_limit = _dec(data["credit_limit"], "credit_limit")
        except ValidationError as exc:
            return _err(exc)
    if not company.name:
        return json_error("name required.")
    company.save()
    return json_ok(_company_row(company))


@api_login_required
@api_role_required(*FRONT_OFFICE, *FINANCE, TenantMembership.Role.MANAGER)
@require_http_methods(["GET", "POST", "PATCH"])
def referrer_update(request, pk):
    ref = BookingReferrer.objects.filter(pk=pk, tenant=request.tenant).first()
    if ref is None:
        return json_error("Referrer not found.", status=404)
    if request.method == "GET":
        return json_ok(_referrer_row(ref))
    data = parse_json(request)
    if "name" in data:
        ref.name = (data.get("name") or "").strip() or ref.name
    if "phone" in data:
        ref.phone = (data.get("phone") or "").strip()
    if "notes" in data:
        ref.notes = (data.get("notes") or "").strip()
    if "is_active" in data:
        ref.is_active = bool(data["is_active"])
    if "default_commission_percent" in data and data["default_commission_percent"] not in (
        None,
        "",
    ):
        try:
            ref.default_commission_percent = _dec(
                data["default_commission_percent"], "default_commission_percent"
            )
        except ValidationError as exc:
            return _err(exc)
    ref.save()
    return json_ok(_referrer_row(ref))


# ── City ledger detail / PDF ─────────────────────────────────────────────────


@api_login_required
@api_role_required(*FINANCE, TenantMembership.Role.MANAGER, TenantMembership.Role.RECEPTIONIST)
@require_GET
def city_ledger_detail(request, pk):
    from folio.models import CompanyInvoice
    from folio.pdf import build_company_invoice_pdf

    invoice = (
        CompanyInvoice.objects.filter(pk=pk, tenant=request.tenant)
        .select_related("company", "hotel")
        .prefetch_related("lines", "payments")
        .first()
    )
    if invoice is None:
        return json_error("Invoice not found.", status=404)

    lines = [
        {
            "id": ln.pk,
            "description": ln.description,
            "amount": str(ln.amount),
        }
        for ln in invoice.lines.all().order_by("id")
    ]
    payments = [
        {
            "id": p.pk,
            "amount": str(p.amount),
            "method": p.method,
            "note": p.note or "",
            "paid_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in invoice.payments.filter(is_void=False).order_by("id")
    ]

    payload = {
        "id": invoice.pk,
        "code": invoice.code,
        "status": invoice.status,
        "company": {
            "id": invoice.company_id,
            "name": invoice.company.name if invoice.company_id else "",
        },
        "total": str(invoice.lines_total),
        "balance": str(invoice.balance),
        "issued_at": invoice.issued_at.isoformat() if invoice.issued_at else None,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "lines": lines,
        "payments": payments,
    }
    if (request.GET.get("pdf") or "").strip() in ("1", "true", "yes"):
        payload["pdf_base64"] = base64.b64encode(
            build_company_invoice_pdf(invoice)
        ).decode("ascii")
        payload["filename"] = f"{invoice.code or f'invoice-{invoice.pk}'}.pdf"
    return json_ok(payload)


# ── Profit share ─────────────────────────────────────────────────────────────


@api_login_required
@api_role_required(*ACCOUNTING, TenantMembership.Role.MANAGER)
@require_GET
def profit_ledger(request):
    from finance.profit import build_partner_ledger, serialize_ledger_snapshot

    hotel = getattr(request, "active_property", None)
    ledger = build_partner_ledger(tenant=request.tenant, hotel=hotel)
    snap = serialize_ledger_snapshot(ledger)
    # Enrich partner rows with ids for withdraw UI
    rows = []
    for row in ledger.get("rows") or []:
        if row.get("inactive"):
            continue
        p = row["partner"]
        rows.append(
            {
                "partner_id": p.pk,
                "name": p.name,
                "share_percent": str(row.get("share_percent") or 0),
                "entitled": str(row.get("entitled") or 0),
                "withdrawn": str(row.get("withdrawn") or 0),
                "remaining": str(row.get("remaining") or 0),
            }
        )
    snap["rows"] = rows
    snap["start"] = str(ledger.get("start") or "")
    snap["end"] = str(ledger.get("end") or "")
    return json_ok(snap)


@api_login_required
@api_role_required(*ACCOUNTING, TenantMembership.Role.MANAGER)
@require_GET
def profit_partners(request):
    from finance.models import ProfitPartner

    qs = ProfitPartner.objects.filter(tenant=request.tenant).order_by("-is_active", "name")
    items = [
        {
            "id": p.pk,
            "name": p.name,
            "share_percent": str(p.share_percent),
            "phone": p.phone or "",
            "notes": p.notes or "",
            "is_active": p.is_active,
        }
        for p in qs[:100]
    ]
    return json_ok({"items": items})


@api_login_required
@api_role_required(*ACCOUNTING, TenantMembership.Role.MANAGER)
@require_POST
def profit_partner_create(request):
    from finance.models import ProfitPartner

    data = parse_json(request)
    name = (data.get("name") or "").strip()
    if not name:
        return json_error("name required.")
    try:
        pct = _dec(data.get("share_percent") or "0", "share_percent")
    except ValidationError as exc:
        return _err(exc)
    partner = ProfitPartner.objects.create(
        tenant=request.tenant,
        name=name,
        share_percent=pct,
        phone=(data.get("phone") or "").strip(),
        notes=(data.get("notes") or "").strip(),
        is_active=True,
    )
    return json_ok(
        {
            "id": partner.pk,
            "name": partner.name,
            "share_percent": str(partner.share_percent),
            "is_active": partner.is_active,
        },
        status=201,
    )


@api_login_required
@api_role_required(*ACCOUNTING, TenantMembership.Role.MANAGER)
@require_http_methods(["POST", "PATCH"])
def profit_partner_update(request, pk):
    from finance.models import ProfitPartner

    partner = ProfitPartner.objects.filter(pk=pk, tenant=request.tenant).first()
    if partner is None:
        return json_error("Partner not found.", status=404)
    data = parse_json(request)
    if "name" in data:
        partner.name = (data.get("name") or "").strip() or partner.name
    if "phone" in data:
        partner.phone = (data.get("phone") or "").strip()
    if "notes" in data:
        partner.notes = (data.get("notes") or "").strip()
    if "is_active" in data:
        partner.is_active = bool(data["is_active"])
    if "share_percent" in data and data["share_percent"] not in (None, ""):
        try:
            partner.share_percent = _dec(data["share_percent"], "share_percent")
        except ValidationError as exc:
            return _err(exc)
    partner.save()
    return json_ok(
        {
            "id": partner.pk,
            "name": partner.name,
            "share_percent": str(partner.share_percent),
            "phone": partner.phone or "",
            "is_active": partner.is_active,
        }
    )


@api_login_required
@api_role_required(*ACCOUNTING, TenantMembership.Role.MANAGER)
@require_POST
def profit_withdraw(request):
    from finance.models import ProfitPartner, ProfitWithdrawal
    from finance.profit import record_withdrawal

    data = parse_json(request)
    partner_id = data.get("partner_id")
    if not partner_id:
        return json_error("partner_id required.")
    partner = ProfitPartner.objects.filter(
        pk=partner_id, tenant=request.tenant, is_active=True
    ).first()
    if partner is None:
        return json_error("Partner not found.", status=404)
    try:
        amount = _dec(data.get("amount"), "amount")
    except ValidationError as exc:
        return _err(exc)
    method = (data.get("method") or ProfitWithdrawal.PaymentMethod.CASH).strip()
    try:
        w = record_withdrawal(
            request.tenant,
            request.user,
            partner=partner,
            amount=amount,
            payment_method=method,
            note=(data.get("note") or "").strip(),
            allow_overdraw=bool(data.get("allow_overdraw")),
            currency=(data.get("currency") or None),
        )
        return json_ok(
            {
                "withdrawal_id": w.pk,
                "amount": str(w.amount),
                "partner_id": partner.pk,
            },
            status=201,
        )
    except ValidationError as exc:
        return _err(exc)


@api_login_required
@api_role_required(*ACCOUNTING, TenantMembership.Role.MANAGER)
@require_POST
def profit_reset(request):
    from finance.profit import reset_profit_period

    data = parse_json(request)
    ended = None
    if data.get("ended_on"):
        try:
            ended = date.fromisoformat(str(data["ended_on"]).strip())
        except ValueError:
            return json_error("Invalid ended_on.")
    try:
        closed, opened = reset_profit_period(
            request.tenant, request.user, ended_on=ended, restart_today=True
        )
        return json_ok(
            {
                "closed_period_id": closed.pk,
                "closed_ended_on": closed.ended_on.isoformat()
                if closed.ended_on
                else None,
                "new_period_id": opened.pk,
                "new_started_on": opened.started_on.isoformat(),
            }
        )
    except ValidationError as exc:
        return _err(exc)


# ── Rate matrix ──────────────────────────────────────────────────────────────


@api_login_required
@api_role_required(*OPS_MANAGER, TenantMembership.Role.MANAGER)
@require_GET
def rate_plan_matrix(request, pk):
    from properties.models import RatePlan
    from properties.services import build_rate_matrix

    hotel = getattr(request, "active_property", None)
    qs = RatePlan.objects.filter(pk=pk, tenant=request.tenant)
    if hotel is not None:
        qs = qs.filter(property=hotel)
    rp = qs.first()
    if rp is None:
        return json_error("Rate plan not found.", status=404)
    start = timezone.localdate()
    if request.GET.get("start"):
        try:
            start = date.fromisoformat(str(request.GET.get("start")).strip())
        except ValueError:
            return json_error("Invalid start date.")
    try:
        days = max(7, min(90, int(request.GET.get("days") or 42)))
    except (TypeError, ValueError):
        days = 42
    rows = build_rate_matrix(rp, start, days=days)
    return json_ok(
        {
            "rate_plan_id": rp.pk,
            "name": rp.name,
            "start": start.isoformat(),
            "days": days,
            "rows": [
                {
                    "date": r["date"].isoformat(),
                    "price": str(r["price"]),
                    "season": r["season"] or "",
                    "is_season": bool(r["is_season"]),
                    "weekday": r["weekday"],
                }
                for r in rows
            ],
        }
    )
