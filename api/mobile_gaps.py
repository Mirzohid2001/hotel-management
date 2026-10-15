"""Mobile-only gaps vs the web desk: purge, guest/account delete, logo, branch, widget, rate day, spends, payroll item."""

from __future__ import annotations

import base64
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from bookings.models import Reservation
from bookings.services import purge_reservation
from core.roles import FRONT_OFFICE, HR, OPS_MANAGER, PROPERTY_ADMIN, TENANT_ADMIN
from guests.models import Guest
from properties.models import Property, PropertySettings, RatePlan, SeasonRate
from tenants.models import TenantMembership

from .auth import api_login_required, api_role_required, json_error, json_ok, parse_json
from .print_parity import _build_statement_pdf


def _err(exc: Exception, status=400):
    if isinstance(exc, ValidationError):
        return json_error("; ".join(exc.messages), status=status)
    return json_error(str(exc), status=status)


def _dec(value, label="amount") -> Decimal:
    try:
        return Decimal(str(value).replace(",", ".").replace(" ", ""))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(f"Invalid {label}.")


@api_login_required
@api_role_required(*TENANT_ADMIN)
@require_POST
def reservation_purge(request, pk):
    reservation = Reservation.objects.filter(pk=pk, tenant=request.tenant).first()
    if reservation is None:
        return json_error("Reservation not found.", status=404)
    try:
        code = purge_reservation(reservation, request.user)
    except ValidationError as exc:
        return _err(exc)
    return json_ok({"code": code, "deleted": True})


@api_login_required
@api_role_required(*FRONT_OFFICE)
@require_POST
def guest_delete(request, pk):
    guest = Guest.objects.filter(pk=pk, tenant=request.tenant).first()
    if guest is None:
        return json_error("Guest not found.", status=404)
    if (
        Reservation.objects.filter(tenant=request.tenant)
        .filter(Q(guest=guest) | Q(occupants__guest=guest))
        .exists()
    ):
        return json_error(
            "Bu mehmonda bron tarixi bor — o‘chirib bo‘lmaydi. "
            "Kelmasa: bronni «Kelmagan» qiling.",
            status=400,
        )
    name = guest.full_name
    try:
        guest.delete()
    except ProtectedError:
        return json_error("Mehmon bog‘liq yozuvlar tufayli o‘chirilmadi.", status=400)
    return json_ok({"deleted": True, "name": name})


@api_login_required
@require_POST
def profile_delete(request):
    user = request.user
    membership = request.membership
    if membership.role == TenantMembership.Role.ADMIN:
        other_admins = (
            TenantMembership.objects.filter(
                tenant_id=membership.tenant_id,
                role=TenantMembership.Role.ADMIN,
                is_active=True,
            )
            .exclude(user_id=user.pk)
            .exists()
        )
        if not other_admins and not user.is_superuser:
            return json_error(
                "Yagona admin akkauntini o‘chirib bo‘lmaydi. Avval boshqa admin qo‘shing.",
                status=400,
            )
    TenantMembership.objects.filter(user=user).update(is_active=False)
    user.is_active = False
    user.save(update_fields=["is_active"])
    if getattr(request, "api_token", None) is not None:
        request.api_token.delete()
    return json_ok({"deleted": True})


@api_login_required
@api_role_required(*TENANT_ADMIN)
@require_http_methods(["GET", "POST"])
def tenant_logo(request):
    tenant = request.tenant
    if request.method == "GET":
        return json_ok(
            {
                "has_logo": bool(tenant.logo),
                "url": tenant.logo.url if tenant.logo else "",
            }
        )
    data = parse_json(request) if request.content_type and "json" in request.content_type else {}
    if data.get("clear") or request.POST.get("clear") in {"1", "true", "yes"}:
        if tenant.logo:
            tenant.logo.delete(save=False)
        tenant.logo = None
        tenant.save(update_fields=["logo"])
        return json_ok({"has_logo": False, "url": ""})
    upload = request.FILES.get("logo")
    if upload is None:
        return json_error("logo file required.")
    if upload.size > 2 * 1024 * 1024:
        return json_error("Logo 2 MB dan kichik bo‘lsin.")
    content = (upload.content_type or "").lower()
    if content and not content.startswith("image/"):
        return json_error("Faqat rasm fayli.")
    if tenant.logo:
        tenant.logo.delete(save=False)
    tenant.logo = upload
    tenant.save(update_fields=["logo"])
    return json_ok({"has_logo": True, "url": tenant.logo.url})


@api_login_required
@api_role_required(*PROPERTY_ADMIN)
@require_POST
def property_create(request):
    data = parse_json(request)
    name = (data.get("name") or "").strip()
    if not name:
        return json_error("name required.")
    active_count = Property.objects.filter(tenant=request.tenant, is_active=True).count()
    if not request.tenant.check_limit("properties", active_count):
        return json_error("Tarif bo‘yicha filiallar limiti tugagan.", status=400)
    if Property.objects.filter(tenant=request.tenant, name=name).exists():
        return json_error("Bu nomdagi filial bor.", status=400)
    branch = (data.get("branch_code") or "").strip().lower().replace(" ", "-")
    if branch and Property.objects.filter(tenant=request.tenant, branch_code=branch).exists():
        return json_error("Bu filial kodi band.", status=400)
    prop = Property.objects.create(
        tenant=request.tenant,
        name=name,
        branch_code=branch,
        address=(data.get("address") or "").strip(),
        city=(data.get("city") or "").strip(),
        phone=(data.get("phone") or "").strip(),
        email=(data.get("email") or "").strip(),
        is_active=True,
    )
    PropertySettings.objects.create(tenant=request.tenant, property=prop)
    return json_ok(
        {"id": prop.pk, "name": prop.name, "branch_code": prop.branch_code},
        status=201,
    )


def _widget_payload(cfg) -> dict:
    return {
        "id": cfg.pk,
        "hotel_id": cfg.hotel_id,
        "is_enabled": cfg.is_enabled,
        "allowed_domains": cfg.allowed_domains,
        "auto_confirm": cfg.auto_confirm,
        "auto_assign_room": cfg.auto_assign_room,
        "welcome_title": cfg.welcome_title,
        "welcome_text": cfg.welcome_text,
        "public_key": cfg.public_key,
        "path": cfg.widget_path,
        "embed_iframe": cfg.embed_iframe_html,
        "embed_script": cfg.embed_script_html,
    }


@api_login_required
@api_role_required(*PROPERTY_ADMIN)
@require_http_methods(["GET", "POST"])
def widget_config(request):
    from widget.models import WidgetConfig

    hotel = getattr(request, "active_property", None)
    data = parse_json(request) if request.method == "POST" else {}
    hotel_id = data.get("hotel_id") or request.GET.get("hotel_id")
    if hotel is None and hotel_id:
        hotel = Property.objects.filter(
            pk=hotel_id, tenant=request.tenant, is_active=True
        ).first()
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    cfg, _created = WidgetConfig.objects.get_or_create(
        hotel=hotel,
        defaults={"tenant": request.tenant},
    )
    if request.method == "GET":
        return json_ok(_widget_payload(cfg))
    if "is_enabled" in data:
        cfg.is_enabled = bool(data.get("is_enabled"))
    if "allowed_domains" in data:
        cfg.allowed_domains = (data.get("allowed_domains") or "").strip()
    if "auto_confirm" in data:
        cfg.auto_confirm = bool(data.get("auto_confirm"))
    if "auto_assign_room" in data:
        cfg.auto_assign_room = bool(data.get("auto_assign_room"))
    if "welcome_title" in data:
        cfg.welcome_title = (data.get("welcome_title") or "")[:200]
    if "welcome_text" in data:
        cfg.welcome_text = (data.get("welcome_text") or "")[:500]
    cfg.tenant = request.tenant
    cfg.save()
    return json_ok(_widget_payload(cfg))


@api_login_required
@api_role_required(*PROPERTY_ADMIN, TenantMembership.Role.MANAGER)
@require_POST
def rate_plan_set_day(request, pk):
    rp = RatePlan.objects.filter(pk=pk, tenant=request.tenant).first()
    if rp is None:
        return json_error("Rate plan not found.", status=404)
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    if rp.property_id != hotel.pk:
        return json_error("Rate plan belongs to another hotel.", status=404)
    data = parse_json(request)
    try:
        day = date.fromisoformat(str(data.get("date") or "").strip())
    except ValueError:
        return json_error("Invalid date.")
    try:
        price = _dec(data.get("price"), "price")
    except ValidationError as exc:
        return _err(exc)
    if price < 0:
        return json_error("Narx manfiy bo‘lmasin.")
    name = (data.get("name") or day.isoformat()).strip()[:120]
    with transaction.atomic():
        row = SeasonRate.objects.filter(
            rate_plan=rp, date_from=day, date_to=day
        ).first()
        if row is None:
            row = SeasonRate(
                tenant=request.tenant,
                rate_plan=rp,
                name=name,
                date_from=day,
                date_to=day,
                price=price,
            )
        else:
            row.name = name
            row.price = price
        row.full_clean()
        row.save()
    return json_ok(
        {
            "id": row.pk,
            "date": day.isoformat(),
            "price": str(row.price),
            "name": row.name,
        }
    )


def _spend_row(expense) -> dict:
    return {
        "id": expense.pk,
        "title": expense.title,
        "amount": str(expense.amount),
        "currency": expense.currency or "",
        "status": expense.status,
        "expense_date": expense.expense_date.isoformat() if expense.expense_date else "",
        "ticket_id": expense.maintenance_ticket_id,
    }


def _spend_qs(request):
    from maintenance.services import maintenance_expense_qs

    hotel = getattr(request, "active_property", None)
    return maintenance_expense_qs(request.tenant, hotel=hotel)


@api_login_required
@api_role_required(*OPS_MANAGER)
@require_GET
def maintenance_spends(request):
    rows = [_spend_row(e) for e in _spend_qs(request).order_by("-expense_date", "-id")[:80]]
    return json_ok({"items": rows})


@api_login_required
@api_role_required(*OPS_MANAGER)
@require_POST
def maintenance_spend_void(request, pk):
    from maintenance.services import void_maintenance_spend

    expense = _spend_qs(request).filter(pk=pk).first()
    if expense is None:
        return json_error("Expense not found.", status=404)
    data = parse_json(request)
    try:
        void_maintenance_spend(expense, request.user, reason=(data.get("reason") or "").strip())
    except ValidationError as exc:
        return _err(exc)
    expense.refresh_from_db()
    return json_ok(_spend_row(expense))


@api_login_required
@api_role_required(*OPS_MANAGER)
@require_POST
def maintenance_spend_delete(request, pk):
    from finance.services import delete_expense

    expense = _spend_qs(request).filter(pk=pk).first()
    if expense is None:
        return json_error("Expense not found.", status=404)
    try:
        delete_expense(expense, request.user)
    except ValidationError as exc:
        return _err(exc)
    return json_ok({"deleted": True, "id": pk})


@api_login_required
@api_role_required(*OPS_MANAGER)
@require_GET
def maintenance_spend_print(request, pk):
    expense = _spend_qs(request).filter(pk=pk).first()
    if expense is None:
        return json_error("Expense not found.", status=404)
    hotel_name = expense.hotel.name if expense.hotel_id else request.tenant.name
    pdf = _build_statement_pdf(
        hotel_name=hotel_name,
        title="Ta’mir xarajati",
        subtitle=expense.expense_date.isoformat() if expense.expense_date else "",
        rows=[
            ("Nomi", expense.title),
            ("Summa", f"{expense.amount} {expense.currency or ''}"),
            ("Holat", expense.status),
            ("Sana", expense.expense_date.isoformat() if expense.expense_date else ""),
        ],
    )
    return json_ok(
        {
            "pdf_base64": base64.b64encode(pdf).decode("ascii"),
            "filename": f"tamir-{expense.pk}.pdf",
            "mime_type": "application/pdf",
        }
    )


@api_login_required
@api_role_required(*OPS_MANAGER)
@require_GET
def maintenance_statement_print(request):
    """Monthly maintenance statement PDF — same data as web statement view."""
    from django.utils import timezone
    from maintenance.services import build_maintenance_statement

    today = timezone.localdate()
    try:
        year = int(request.GET.get("year") or today.year)
        month = int(request.GET.get("month") or today.month)
    except (TypeError, ValueError):
        return json_error("Invalid year/month.")
    hotel = getattr(request, "active_property", None)
    data = build_maintenance_statement(
        request.tenant, year=year, month=month, hotel=hotel
    )
    hotel_name = hotel.name if hotel is not None else request.tenant.name
    currency = request.tenant.currency or "UZS"
    rows: list[tuple[str, str]] = [
        ("Yozuvlar", str(data.get("count") or 0)),
        ("Joriy", f"{data.get('operating_total') or 0} {currency}"),
        ("Reinvestitsiya", f"{data.get('reinvest_total') or 0} {currency}"),
        ("Jami", f"{data.get('grand_total') or 0} {currency}"),
    ]
    for row in data.get("rows") or []:
        label = f"{row.get('date') or ''} · {row.get('title') or ''}"
        if row.get("room"):
            label += f" · {row['room']}"
        amount = f"{row.get('amount') or 0} · {row.get('funding_label') or ''}"
        rows.append((label.strip(" ·"), amount))
    pdf = _build_statement_pdf(
        hotel_name=hotel_name,
        title="Ta’mir bayonnomasi",
        subtitle=f"{year}-{month:02d}",
        rows=rows,
    )
    return json_ok(
        {
            "pdf_base64": base64.b64encode(pdf).decode("ascii"),
            "filename": f"tamir-bayon-{year}-{month:02d}.pdf",
            "mime_type": "application/pdf",
            "year": year,
            "month": month,
            "count": data.get("count") or 0,
            "grand_total": str(data.get("grand_total") or 0),
        }
    )


@api_login_required
@api_role_required(*HR)
@require_GET
def payroll_items(request):
    from hr.models import PayrollItem, PayrollPeriod, SalaryPayment

    today = date.today()
    try:
        year = int(request.GET.get("year") or today.year)
        month = int(request.GET.get("month") or today.month)
    except (TypeError, ValueError):
        return json_error("Invalid year/month.")
    period = PayrollPeriod.objects.filter(
        tenant=request.tenant, year=year, month=month
    ).first()
    if period is None:
        return json_ok({"year": year, "month": month, "items": []})
    paid_ids = set(
        SalaryPayment.objects.filter(item__period=period).values_list("item_id", flat=True)
    )
    items = []
    for item in PayrollItem.objects.filter(period=period).select_related("employee"):
        items.append(
            {
                "id": item.pk,
                "employee": item.employee.full_name,
                "bonus": str(item.bonus),
                "deduction": str(item.deduction),
                "net_amount": str(item.net_amount),
                "paid": item.pk in paid_ids,
            }
        )
    return json_ok({"year": year, "month": month, "items": items})


@api_login_required
@api_role_required(*HR)
@require_POST
def payroll_item_update(request, pk):
    from hr.models import PayrollItem
    from hr.services import update_payroll_item_amounts

    item = (
        PayrollItem.objects.filter(pk=pk, tenant=request.tenant)
        .select_related("employee", "period")
        .first()
    )
    if item is None:
        return json_error("Payroll item not found.", status=404)
    data = parse_json(request)
    try:
        bonus = _dec(data["bonus"], "bonus") if "bonus" in data and data["bonus"] not in (None, "") else None
        deduction = (
            _dec(data["deduction"], "deduction")
            if "deduction" in data and data["deduction"] not in (None, "")
            else None
        )
        update_payroll_item_amounts(item, bonus=bonus, deduction=deduction)
    except ValidationError as exc:
        return _err(exc)
    item.refresh_from_db()
    return json_ok(
        {
            "id": item.pk,
            "employee": item.employee.full_name,
            "bonus": str(item.bonus),
            "deduction": str(item.deduction),
            "net_amount": str(item.net_amount),
        }
    )
