"""P3 parity: staff invite/edit, audit log, CSV export, e-mehmon report.

Additive JSON API — web HTML/views untouched.
"""

from __future__ import annotations

import base64
import csv
import io
from datetime import date

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from bookings.emehmon import build_emehmon_report
from core.models import ActivityLog
from core.roles import ACCOUNTING, AUDIT, STAFF_ADMIN
from folio.city_ledger import ar_aging
from folio.models import GuestPayment
from properties.models import Property
from reports.accounting import build_pnl_report, guest_ar_summary
from tenants.forms import save_membership_properties
from tenants.models import TenantMembership

from .auth import api_login_required, api_role_required, json_error, json_ok, parse_json

User = get_user_model()


def _member_row(m: TenantMembership) -> dict:
    props = [
        {"id": p.pk, "name": p.name}
        for p in Property.objects.filter(
            pk__in=m.assigned_property_ids(), tenant=m.tenant
        ).order_by("name")
    ]
    return {
        "id": m.pk,
        "user_id": m.user_id,
        "username": m.user.get_username(),
        "full_name": m.user.get_full_name() or m.user.get_username(),
        "email": m.user.email or "",
        "role": m.role,
        "is_active": m.is_active,
        "properties": props,
        "all_properties": len(props) == 0,
    }


@api_login_required
@api_role_required(*STAFF_ADMIN)
@require_GET
def staff_meta(request):
    props = [
        {"id": p.pk, "name": p.name, "branch_code": getattr(p, "branch_code", "") or ""}
        for p in Property.objects.filter(tenant=request.tenant, is_active=True).order_by(
            "name"
        )
    ]
    roles = [{"id": c[0], "label": str(c[1])} for c in TenantMembership.Role.choices]
    return json_ok({"roles": roles, "properties": props})


@api_login_required
@api_role_required(*STAFF_ADMIN)
@require_GET
def staff_list(request):
    members = (
        TenantMembership.objects.filter(tenant=request.tenant)
        .select_related("user")
        .prefetch_related("property_assignments__property")
        .order_by("role", "user__username")
    )
    return json_ok({"items": [_member_row(m) for m in members]})


@api_login_required
@api_role_required(*STAFF_ADMIN)
@require_POST
def staff_invite(request):
    data = parse_json(request)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    role = (data.get("role") or "").strip()
    if not username or len(password) < 8:
        return json_error("username and password (min 8) required.")
    if role not in dict(TenantMembership.Role.choices):
        return json_error("Invalid role.")
    if not request.tenant.check_limit(
        "users",
        TenantMembership.objects.filter(tenant=request.tenant, is_active=True).count(),
    ):
        return json_error("User limit reached for current plan.", status=403)

    prop_ids = data.get("property_ids") or []
    if not isinstance(prop_ids, list):
        return json_error("property_ids must be a list.")
    props = list(
        Property.objects.filter(
            tenant=request.tenant, is_active=True, pk__in=prop_ids
        )
    )

    with transaction.atomic():
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": (data.get("email") or "").strip(),
                "first_name": (data.get("first_name") or "").strip(),
                "last_name": (data.get("last_name") or "").strip(),
            },
        )
        if created:
            user.set_password(password)
            user.save()
        membership, mem_created = TenantMembership.objects.get_or_create(
            user=user,
            tenant=request.tenant,
            defaults={"role": role, "is_active": True},
        )
        if not mem_created:
            membership.role = role
            membership.is_active = True
            membership.save()
        save_membership_properties(membership, props)

    return json_ok(_member_row(membership), status=201)


@api_login_required
@api_role_required(*STAFF_ADMIN)
@require_http_methods(["POST", "PATCH"])
def staff_update(request, pk):
    membership = (
        TenantMembership.objects.filter(pk=pk, tenant=request.tenant)
        .select_related("user")
        .first()
    )
    if membership is None:
        return json_error("Staff not found.", status=404)
    data = parse_json(request)
    if "role" in data and data["role"] not in (None, ""):
        role = str(data["role"]).strip()
        if role not in dict(TenantMembership.Role.choices):
            return json_error("Invalid role.")
        membership.role = role
    if "is_active" in data:
        membership.is_active = bool(data["is_active"])
    membership.save()
    if "property_ids" in data:
        raw = data.get("property_ids") or []
        if not isinstance(raw, list):
            return json_error("property_ids must be a list.")
        props = list(
            Property.objects.filter(
                tenant=request.tenant, is_active=True, pk__in=raw
            )
        )
        save_membership_properties(membership, props)
    membership.refresh_from_db()
    return json_ok(_member_row(membership))


@api_login_required
@api_role_required(*AUDIT, TenantMembership.Role.MANAGER)
@require_GET
def audit_log(request):
    qs = ActivityLog.objects.filter(tenant=request.tenant).select_related("user")
    action = (request.GET.get("action") or "").strip()
    if action:
        qs = qs.filter(action__icontains=action)
    user_id = request.GET.get("user_id")
    if user_id:
        try:
            qs = qs.filter(user_id=int(user_id))
        except (TypeError, ValueError):
            return json_error("Invalid user_id.")
    try:
        limit = min(max(int(request.GET.get("limit") or 200), 1), 500)
    except (TypeError, ValueError):
        limit = 200
    items = [
        {
            "id": log.pk,
            "action": log.action,
            "model": log.model,
            "object_id": log.object_id,
            "payload": log.payload or {},
            "user": log.user.get_username() if log.user_id else None,
            "user_id": log.user_id,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in qs.order_by("-created_at")[:limit]
    ]
    return json_ok({"items": items})


def _csv_response(filename: str, rows: list[list]) -> dict:
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    raw = buf.getvalue().encode("utf-8-sig")
    return {
        "filename": filename,
        "mime_type": "text/csv",
        "content_base64": base64.b64encode(raw).decode("ascii"),
        "bytes": len(raw),
    }


@api_login_required
@api_role_required(*ACCOUNTING)
@require_GET
def export_payments_csv(request):
    rows: list[list] = [["date", "reservation", "method", "kind", "amount"]]
    qs = (
        GuestPayment.objects.filter(tenant=request.tenant, is_void=False)
        .select_related("folio__reservation")
        .order_by("-created_at")[:2000]
    )
    for p in qs:
        rows.append(
            [
                p.created_at.date().isoformat(),
                p.folio.reservation.code if p.folio_id and p.folio.reservation_id else "",
                p.method,
                p.kind,
                str(p.amount),
            ]
        )
    return json_ok(_csv_response("payments.csv", rows))


@api_login_required
@api_role_required(*ACCOUNTING)
@require_GET
def export_pnl_csv(request):
    today = timezone.localdate()
    try:
        year = int(request.GET.get("year") or today.year)
        month = int(request.GET.get("month") or today.month)
    except (TypeError, ValueError):
        return json_error("Invalid year/month.")
    basis = (request.GET.get("basis") or "cash").strip()
    hotel = getattr(request, "active_property", None)
    report = build_pnl_report(request.tenant, year, month, basis=basis, hotel=hotel)
    rows: list[list] = [["section", "label", "amount"]]
    rows.append(["revenue", "total", str(report["revenue_total"])])
    for row in report["revenue_breakdown"]:
        label = row.get("label", row.get("key", ""))
        rows.append(["revenue", label, str(row["amount"])])
    rows.append(["expense", "total", str(report["expenses_total"])])
    for row in report["expenses_breakdown"]:
        rows.append(["expense", row["label"], str(row["amount"])])
    rows.append(["payroll", "total", str(report["payroll"])])
    rows.append(["advances", "total", str(report["advances"])])
    rows.append(["commission", "total", str(report["commission"])])
    rows.append(["inventory", "total", str(report["inventory_cost"])])
    rows.append(
        ["emehmon_shortfall", "total", str(report.get("emehmon_shortfall") or 0)]
    )
    rows.append(["operating", "total", str(report["operating_costs"])])
    rows.append(["net", "net", str(report["net"])])
    return json_ok(
        _csv_response(f"pnl-{year}-{month:02d}-{basis}.csv", rows)
    )


@api_login_required
@api_role_required(*ACCOUNTING)
@require_GET
def export_ar_csv(request):
    tenant = request.tenant
    aging = ar_aging(tenant)
    guest_ar = guest_ar_summary(tenant)
    rows: list[list] = [["type", "bucket", "code", "name", "balance"]]
    for bucket in aging["buckets"].values():
        for inv in bucket["invoices"]:
            rows.append(
                [
                    "company",
                    bucket["label"],
                    inv.code,
                    inv.company.name,
                    str(inv.balance),
                ]
            )
    for row in guest_ar["rows"]:
        rows.append(
            ["guest", "open_folio", row["code"], row["guest"], str(row["balance"])]
        )
    rows.append(["", "guest_total", "", "", str(guest_ar["total"])])
    rows.append(["", "company_total", "", "", str(aging["grand_total"])])
    return json_ok(_csv_response("ar-aging.csv", rows))


@api_login_required
@api_role_required(*ACCOUNTING)
@require_GET
def emehmon_report(request):
    today = timezone.localdate()
    try:
        year = int(request.GET.get("year") or today.year)
        month = int(request.GET.get("month") or today.month)
    except (TypeError, ValueError):
        return json_error("Invalid year/month.")
    hotel = getattr(request, "active_property", None)
    report = build_emehmon_report(
        request.tenant, year=year, month=month, hotel=hotel
    )
    # Decimal / date / models → JSON-safe
    def _ser(v):
        if hasattr(v, "quantize"):
            return str(v)
        if isinstance(v, list):
            return [_ser(x) for x in v]
        if isinstance(v, dict):
            return {k: _ser(x) for k, x in v.items()}
        if isinstance(v, date):
            return v.isoformat()
        if hasattr(v, "pk") and hasattr(v, "_meta"):
            # Django model — keep id + common labels
            out = {"id": v.pk}
            for attr in ("code", "name", "full_name", "title", "number"):
                if hasattr(v, attr):
                    val = getattr(v, attr)
                    if callable(val):
                        try:
                            val = val()
                        except Exception:  # noqa: BLE001
                            continue
                    if val is not None:
                        out[attr] = str(val) if not isinstance(val, (str, int, float, bool)) else val
            return out
        return v

    return json_ok(_ser(report))
