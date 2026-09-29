"""P2 parity: inventory, referrers/commission, HR."""

from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from bookings.commission import (
    active_referrers,
    build_commission_report,
    record_commission_payment,
)
from bookings.models import BookingReferrer, ReferrerCommissionPayment
from core.roles import ACCOUNTING, FRONT_OFFICE, HR, INVENTORY
from hr.services import (
    create_advance,
    finalize_payroll,
    generate_payroll,
    open_advance_total,
    pay_all_unpaid,
    pay_employee_daily,
    pay_employee_salary,
    salary_due_preview,
    settle_advance,
)
from hr.models import Employee, PayrollPeriod, SalaryAdvance
from inventory.models import StockItem, StockMovement
from inventory.services import (
    adjust_stock,
    expired_stock_items,
    expiring_soon_stock_items,
    low_stock_items,
)

from .auth import api_login_required, api_role_required, json_error, json_ok, parse_json


def _err(exc):
    if hasattr(exc, "message_dict"):
        msgs = []
        for v in exc.message_dict.values():
            msgs.extend(v if isinstance(v, (list, tuple)) else [v])
        return json_error("; ".join(str(m) for m in msgs) or str(exc))
    if hasattr(exc, "messages"):
        return json_error("; ".join(str(m) for m in exc.messages))
    return json_error(str(exc))


def _dec(v, field="amount"):
    try:
        return Decimal(str(v).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(f"Valid {field} required.")


def _stock_row(item: StockItem, *, low_ids=None) -> dict:
    low_ids = low_ids or set()
    return {
        "id": item.pk,
        "name": item.name,
        "sku": item.sku,
        "unit": item.unit,
        "quantity_on_hand": str(item.quantity_on_hand),
        "reorder_level": str(item.reorder_level),
        "unit_cost": str(item.unit_cost),
        "sell_price": str(item.sell_price),
        "currency": item.currency,
        "expiry_date": item.expiry_date.isoformat() if item.expiry_date else None,
        "expiry_status": item.expiry_status(),
        "is_minibar": item.is_minibar,
        "is_active": item.is_active,
        "is_low": item.pk in low_ids
        or (
            item.is_active
            and item.reorder_level > 0
            and item.quantity_on_hand <= item.reorder_level
        ),
    }


def _hotel_stock_qs(request):
    hotel = getattr(request, "active_property", None)
    qs = StockItem.objects.filter(tenant=request.tenant)
    if hotel is not None:
        qs = qs.filter(hotel=hotel)
    return qs, hotel


@api_login_required
@api_role_required(*INVENTORY)
@require_GET
def inventory_items(request):
    qs, hotel = _hotel_stock_qs(request)
    if (request.GET.get("active") or "1") == "1":
        qs = qs.filter(is_active=True)
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q))
    flag = (request.GET.get("flag") or "").strip()
    low = {i.pk for i in low_stock_items(request.tenant, hotel)}
    if flag == "low":
        qs = qs.filter(pk__in=low)
    elif flag == "minibar":
        qs = qs.filter(is_minibar=True)
    elif flag == "expired":
        qs = expired_stock_items(request.tenant, hotel)
    elif flag == "soon":
        soon_ids = {i.pk for i in expiring_soon_stock_items(request.tenant, hotel)}
        qs = qs.filter(pk__in=soon_ids)
    items = [_stock_row(i, low_ids=low) for i in qs.order_by("name")[:200]]
    return json_ok(
        {
            "items": items,
            "badges": {
                "low": len(low),
                "expired": expired_stock_items(request.tenant, hotel).count(),
                "soon": len(expiring_soon_stock_items(request.tenant, hotel)),
            },
        }
    )


@api_login_required
@api_role_required(*INVENTORY)
@require_POST
def inventory_adjust(request, pk):
    qs, _hotel = _hotel_stock_qs(request)
    item = qs.filter(pk=pk).first()
    if item is None:
        return json_error("Stock item not found.", status=404)
    data = parse_json(request)
    movement_type = (data.get("movement_type") or "").strip().lower()
    if movement_type not in dict(StockMovement.MovementType.choices):
        return json_error("movement_type must be in|out|adjust.")
    try:
        quantity = _dec(data.get("quantity"), "quantity")
        mov = adjust_stock(
            item,
            movement_type=movement_type,
            quantity=quantity,
            user=request.user,
            note=(data.get("note") or "").strip(),
        )
        item.refresh_from_db()
        return json_ok(
            {
                "item_id": item.pk,
                "quantity_on_hand": str(item.quantity_on_hand),
                "movement_id": mov.pk,
                "movement_type": mov.movement_type,
            }
        )
    except ValidationError as exc:
        return _err(exc)


@api_login_required
@api_role_required(*INVENTORY)
@require_GET
def inventory_low_stock(request):
    hotel = getattr(request, "active_property", None)
    low = list(low_stock_items(request.tenant, hotel).order_by("name")[:100])
    low_ids = {i.pk for i in low}
    return json_ok({"items": [_stock_row(i, low_ids=low_ids) for i in low]})


@api_login_required
@api_role_required(*INVENTORY)
@require_POST
def inventory_create(request):
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        return json_error("Select a hotel (X-Hotel-Id).", status=400)
    data = parse_json(request)
    name = (data.get("name") or "").strip()
    sku = (data.get("sku") or "").strip().lower()
    if not name or not sku:
        return json_error("name and sku required.")
    unit = (data.get("unit") or StockItem.Unit.DONA).strip()
    if unit not in dict(StockItem.Unit.choices):
        return json_error("Invalid unit.")
    try:
        item = StockItem(
            tenant=request.tenant,
            hotel=hotel,
            name=name,
            sku=sku,
            unit=unit,
            quantity_on_hand=_dec(data.get("quantity_on_hand") or "0", "quantity"),
            reorder_level=_dec(data.get("reorder_level") or "0", "reorder_level"),
            unit_cost=_dec(data.get("unit_cost") or "0", "unit_cost"),
            sell_price=_dec(data.get("sell_price") or "0", "sell_price"),
            currency=(data.get("currency") or request.tenant.currency or "UZS").upper(),
            is_minibar=bool(data.get("is_minibar")),
            is_active=True,
        )
        if data.get("expiry_date"):
            item.expiry_date = date.fromisoformat(str(data["expiry_date"]).strip())
        item.save()
        return json_ok(_stock_row(item), status=201)
    except ValidationError as exc:
        return _err(exc)
    except (ValueError, TypeError) as exc:
        return json_error(str(exc))


@api_login_required
@api_role_required(*INVENTORY)
@require_POST
def inventory_update(request, pk):
    qs, _hotel = _hotel_stock_qs(request)
    item = qs.filter(pk=pk).first()
    if item is None:
        return json_error("Stock item not found.", status=404)
    data = parse_json(request)
    try:
        if "name" in data:
            item.name = (data.get("name") or "").strip() or item.name
        if "reorder_level" in data and data["reorder_level"] not in (None, ""):
            item.reorder_level = _dec(data["reorder_level"], "reorder_level")
        if "unit_cost" in data and data["unit_cost"] not in (None, ""):
            item.unit_cost = _dec(data["unit_cost"], "unit_cost")
        if "sell_price" in data and data["sell_price"] not in (None, ""):
            item.sell_price = _dec(data["sell_price"], "sell_price")
        if "is_minibar" in data:
            item.is_minibar = bool(data["is_minibar"])
        if "is_active" in data:
            item.is_active = bool(data["is_active"])
        if "expiry_date" in data:
            raw = data.get("expiry_date")
            item.expiry_date = (
                date.fromisoformat(str(raw).strip()) if raw else None
            )
        item.save()
        return json_ok(_stock_row(item))
    except ValidationError as exc:
        return _err(exc)
    except (ValueError, TypeError) as exc:
        return json_error(str(exc))


def _referrer_row(r: BookingReferrer) -> dict:
    return {
        "id": r.pk,
        "name": r.name,
        "phone": r.phone or "",
        "default_commission_percent": str(r.default_commission_percent),
        "notes": r.notes or "",
        "is_active": r.is_active,
    }


@api_login_required
@api_role_required(*FRONT_OFFICE)
@require_GET
def referrers(request):
    qs = active_referrers(request.tenant)
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(phone__icontains=q))
    return json_ok({"items": [_referrer_row(r) for r in qs[:100]]})


@api_login_required
@api_role_required(*FRONT_OFFICE)
@require_POST
def referrer_create(request):
    data = parse_json(request)
    name = (data.get("name") or "").strip()
    if not name:
        return json_error("name required.")
    if BookingReferrer.objects.filter(tenant=request.tenant, name__iexact=name).exists():
        return json_error("Referrer with this name already exists.")
    percent = Decimal("0")
    if data.get("default_commission_percent") not in (None, ""):
        try:
            percent = _dec(data.get("default_commission_percent"), "percent")
        except ValidationError as exc:
            return _err(exc)
    ref = BookingReferrer.objects.create(
        tenant=request.tenant,
        name=name,
        phone=(data.get("phone") or "").strip(),
        default_commission_percent=percent,
        notes=(data.get("notes") or "").strip(),
    )
    return json_ok(_referrer_row(ref), status=201)


@api_login_required
@api_role_required(*ACCOUNTING)
@require_GET
def commission_report(request):
    today = timezone.localdate()
    try:
        year = int(request.GET.get("year") or today.year)
        month = int(request.GET.get("month") or today.month)
    except (TypeError, ValueError):
        return json_error("Invalid year/month.")
    report = build_commission_report(request.tenant, year=year, month=month)
    items = []
    for bucket in report.get("groups", []):
        ref = bucket["referrer"]
        items.append(
            {
                "referrer_id": ref.pk,
                "name": ref.name,
                "phone": ref.phone or "",
                "count": bucket["count"],
                "base_total": str(bucket["base_total"]),
                "commission_total": str(bucket["commission_total"]),
                "paid_total": str(bucket.get("paid_total", 0)),
                "remaining": str(bucket.get("remaining", 0)),
            }
        )
    return json_ok(
        {
            "year": year,
            "month": month,
            "items": items,
            "grand_commission": str(report.get("grand_commission", 0)),
            "grand_paid": str(report.get("grand_paid", 0)),
            "grand_remaining": str(report.get("grand_remaining", 0)),
        }
    )


@api_login_required
@api_role_required(*ACCOUNTING)
@require_POST
def commission_pay(request, pk):
    ref = BookingReferrer.objects.filter(pk=pk, tenant=request.tenant).first()
    if ref is None:
        return json_error("Referrer not found.", status=404)
    data = parse_json(request)
    today = timezone.localdate()
    try:
        year = int(data.get("year") or today.year)
        month = int(data.get("month") or today.month)
        amount = _dec(data.get("amount"))
    except (TypeError, ValueError, ValidationError) as exc:
        return _err(exc) if isinstance(exc, ValidationError) else json_error(str(exc))
    method = (data.get("method") or ReferrerCommissionPayment.Method.CASH).strip()
    if method not in dict(ReferrerCommissionPayment.Method.choices):
        return json_error("Invalid method.")
    try:
        pay = record_commission_payment(
            request.tenant,
            ref,
            year=year,
            month=month,
            amount=amount,
            method=method,
            note=(data.get("note") or "").strip(),
            user=request.user,
        )
        return json_ok(
            {
                "payment_id": pay.pk,
                "amount": str(pay.amount),
                "year": pay.year,
                "month": pay.month,
                "method": pay.method,
            },
            status=201,
        )
    except ValidationError as exc:
        return _err(exc)


def _employee_row(emp: Employee) -> dict:
    open_adv = open_advance_total(emp)
    due = salary_due_preview(emp, days=1)
    return {
        "id": emp.pk,
        "full_name": emp.full_name,
        "position": emp.position or "",
        "salary_type": emp.salary_type,
        "is_daily": emp.is_daily,
        "base_salary": str(emp.base_salary),
        "phone": emp.phone or "",
        "is_active": emp.is_active,
        "open_advance": str(open_adv),
        "due_preview": str(due),
    }


@api_login_required
@api_role_required(*HR)
@require_GET
def hr_employees(request):
    qs = Employee.objects.filter(tenant=request.tenant, is_active=True)
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(full_name__icontains=q) | Q(position__icontains=q) | Q(phone__icontains=q)
        )
    return json_ok({"items": [_employee_row(e) for e in qs.order_by("full_name")[:100]]})


@api_login_required
@api_role_required(*HR)
@require_POST
def hr_advance(request, pk):
    emp = Employee.objects.filter(pk=pk, tenant=request.tenant).first()
    if emp is None:
        return json_error("Employee not found.", status=404)
    data = parse_json(request)
    try:
        amount = _dec(data.get("amount"))
        adv = create_advance(
            request.tenant,
            emp,
            amount=amount,
            note=(data.get("note") or "").strip(),
        )
        return json_ok(
            {
                "advance_id": adv.pk,
                "amount": str(adv.amount),
                "open_advance": str(open_advance_total(emp)),
            },
            status=201,
        )
    except ValidationError as exc:
        return _err(exc)


@api_login_required
@api_role_required(*HR)
@require_POST
def hr_pay(request, pk):
    emp = Employee.objects.filter(pk=pk, tenant=request.tenant).first()
    if emp is None:
        return json_error("Employee not found.", status=404)
    data = parse_json(request)
    method = (data.get("method") or "cash").strip().lower()
    try:
        if emp.is_daily:
            days = int(data.get("days") or 1)
            work_date = None
            if data.get("work_date"):
                work_date = date.fromisoformat(str(data["work_date"]).strip())
            payment = pay_employee_daily(
                request.tenant,
                emp,
                days=days,
                work_date=work_date,
                method=method,
            )
        else:
            year = data.get("year")
            month = data.get("month")
            payment = pay_employee_salary(
                request.tenant,
                emp,
                year=int(year) if year not in (None, "") else None,
                month=int(month) if month not in (None, "") else None,
                method=method,
            )
        return json_ok(
            {
                "payment_id": payment.pk,
                "amount": str(payment.amount),
                "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
                "method": payment.method,
                "open_advance": str(open_advance_total(emp)),
            },
            status=201,
        )
    except (ValidationError, ValueError) as exc:
        return _err(exc) if isinstance(exc, ValidationError) else json_error(str(exc))


@api_login_required
@api_role_required(*HR)
@require_GET
def hr_advances(request):
    qs = SalaryAdvance.objects.filter(tenant=request.tenant).select_related("employee")
    if (request.GET.get("open") or "1") == "1":
        qs = qs.filter(is_settled=False)
    items = [
        {
            "id": a.pk,
            "employee_id": a.employee_id,
            "employee": a.employee.full_name,
            "amount": str(a.amount),
            "open_amount": str(a.open_amount),
            "advance_date": a.advance_date.isoformat() if a.advance_date else None,
            "is_settled": a.is_settled,
            "note": a.note or "",
        }
        for a in qs.order_by("-advance_date", "-id")[:100]
    ]
    return json_ok({"items": items})


@api_login_required
@api_role_required(*HR)
@require_POST
def hr_advance_settle(request, pk):
    adv = SalaryAdvance.objects.filter(pk=pk, tenant=request.tenant).first()
    if adv is None:
        return json_error("Advance not found.", status=404)
    try:
        settle_advance(adv)
        return json_ok({"advance_id": adv.pk, "is_settled": True})
    except ValidationError as exc:
        return _err(exc)


@api_login_required
@api_role_required(*HR)
@require_POST
def hr_employee_create(request):
    data = parse_json(request)
    name = (data.get("full_name") or "").strip()
    if not name:
        return json_error("full_name required.")
    salary_type = (data.get("salary_type") or Employee.SalaryType.MONTHLY).strip()
    if salary_type not in dict(Employee.SalaryType.choices):
        return json_error("Invalid salary_type.")
    try:
        salary = _dec(data.get("base_salary") or "0", "base_salary")
    except ValidationError as exc:
        return _err(exc)
    hire = timezone.localdate()
    if data.get("hire_date"):
        try:
            hire = date.fromisoformat(str(data["hire_date"]).strip())
        except ValueError:
            return json_error("Invalid hire_date.")
    emp = Employee.objects.create(
        tenant=request.tenant,
        full_name=name,
        position=(data.get("position") or "").strip(),
        salary_type=salary_type,
        base_salary=salary,
        hire_date=hire,
        phone=(data.get("phone") or "").strip(),
        is_active=True,
    )
    return json_ok(_employee_row(emp), status=201)


@api_login_required
@api_role_required(*HR)
@require_POST
def hr_employee_update(request, pk):
    emp = Employee.objects.filter(pk=pk, tenant=request.tenant).first()
    if emp is None:
        return json_error("Employee not found.", status=404)
    data = parse_json(request)
    try:
        if "full_name" in data:
            emp.full_name = (data.get("full_name") or "").strip() or emp.full_name
        if "position" in data:
            emp.position = (data.get("position") or "").strip()
        if "phone" in data:
            emp.phone = (data.get("phone") or "").strip()
        if "salary_type" in data:
            st = (data.get("salary_type") or "").strip()
            if st not in dict(Employee.SalaryType.choices):
                return json_error("Invalid salary_type.")
            emp.salary_type = st
        if "base_salary" in data and data["base_salary"] not in (None, ""):
            emp.base_salary = _dec(data["base_salary"], "base_salary")
        if "is_active" in data:
            emp.is_active = bool(data["is_active"])
        emp.save()
        return json_ok(_employee_row(emp))
    except ValidationError as exc:
        return _err(exc)


@api_login_required
@api_role_required(*HR)
@require_GET
def hr_payroll_status(request):
    today = timezone.localdate()
    try:
        year = int(request.GET.get("year") or today.year)
        month = int(request.GET.get("month") or today.month)
    except (TypeError, ValueError):
        return json_error("Invalid year/month.")
    period = PayrollPeriod.objects.filter(
        tenant=request.tenant, year=year, month=month
    ).first()
    return json_ok(
        {
            "year": year,
            "month": month,
            "exists": period is not None,
            "period": (
                {
                    "id": period.pk,
                    "status": period.status,
                    "is_finalized": period.status
                    in (
                        PayrollPeriod.Status.FINALIZED,
                        PayrollPeriod.Status.PAID,
                    ),
                }
                if period
                else None
            ),
        }
    )


@api_login_required
@api_role_required(*HR)
@require_POST
def hr_payroll_generate(request):
    data = parse_json(request)
    today = timezone.localdate()
    try:
        year = int(data.get("year") or today.year)
        month = int(data.get("month") or today.month)
        period = generate_payroll(request.tenant, year, month)
        return json_ok(
            {
                "id": period.pk,
                "year": period.year,
                "month": period.month,
                "status": period.status,
                "items": period.items.count() if hasattr(period, "items") else 0,
            },
            status=201,
        )
    except (ValidationError, TypeError, ValueError) as exc:
        return _err(exc) if isinstance(exc, ValidationError) else json_error(str(exc))


@api_login_required
@api_role_required(*HR)
@require_POST
def hr_payroll_finalize(request, pk):
    period = PayrollPeriod.objects.filter(pk=pk, tenant=request.tenant).first()
    if period is None:
        return json_error("Payroll period not found.", status=404)
    try:
        finalize_payroll(period)
        period.refresh_from_db()
        return json_ok({"id": period.pk, "status": period.status})
    except ValidationError as exc:
        return _err(exc)


@api_login_required
@api_role_required(*HR)
@require_POST
def hr_payroll_pay_all(request):
    data = parse_json(request)
    today = timezone.localdate()
    try:
        year = int(data.get("year") or today.year) if data.get("year") not in (None, "") else None
        month = (
            int(data.get("month") or today.month) if data.get("month") not in (None, "") else None
        )
        method = (data.get("method") or "cash").strip().lower()
        count = pay_all_unpaid(
            request.tenant, year=year, month=month, method=method
        )
        return json_ok({"paid_count": count})
    except (ValidationError, TypeError, ValueError) as exc:
        return _err(exc) if isinstance(exc, ValidationError) else json_error(str(exc))

