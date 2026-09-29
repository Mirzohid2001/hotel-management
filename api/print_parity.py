"""Mobile chek / PDF prints — ReportLab, same brand as folio.pdf."""

from __future__ import annotations

import base64
from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO

from django.utils import timezone
from django.views.decorators.http import require_GET
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.roles import ACCOUNTING, CASH, DASHBOARD, FINANCE, FRONT_OFFICE
from tenants.models import TenantMembership

from .auth import api_login_required, api_role_required, json_error, json_ok

BRAND = colors.HexColor("#c45c26")
INK = colors.HexColor("#1c1814")
MUTED = colors.HexColor("#6f675e")
LINE = colors.HexColor("#d4cbc0")


def _money(amount, currency="UZS") -> str:
    try:
        value = Decimal(str(amount or 0))
    except (InvalidOperation, TypeError, ValueError):
        value = Decimal("0")
    return f"{value:,.2f} {currency}"


def _styles():
    base = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle(
            "ChkBrand",
            parent=base["Normal"],
            fontSize=18,
            textColor=BRAND,
            fontName="Helvetica-Bold",
            spaceAfter=2,
        ),
        "h2": ParagraphStyle(
            "ChkH2",
            parent=base["Normal"],
            fontSize=11,
            textColor=INK,
            fontName="Helvetica-Bold",
            spaceBefore=8,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "ChkBody",
            parent=base["Normal"],
            fontSize=9.5,
            textColor=INK,
        ),
        "muted": ParagraphStyle(
            "ChkMuted",
            parent=base["Normal"],
            fontSize=8.5,
            textColor=MUTED,
        ),
        "right": ParagraphStyle(
            "ChkRight",
            parent=base["Normal"],
            fontSize=9.5,
            textColor=INK,
            alignment=TA_RIGHT,
        ),
    }


def _build_statement_pdf(*, hotel_name: str, title: str, subtitle: str, rows: list[tuple[str, str]]) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    s = _styles()
    story = [
        Paragraph(hotel_name or "Hotel", s["brand"]),
        Paragraph(title, s["h2"]),
        Paragraph(subtitle, s["muted"]),
        Spacer(1, 6),
        HRFlowable(width="100%", thickness=1, color=LINE),
        Spacer(1, 8),
    ]
    data = [[Paragraph(a, s["body"]), Paragraph(b, s["right"])] for a, b in rows]
    if data:
        table = Table(data, colWidths=[110 * mm, 50 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
                ]
            )
        )
        story.append(table)
    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            f"Chop etilgan: {timezone.localtime().strftime('%d.%m.%Y %H:%M')}",
            s["muted"],
        )
    )
    doc.build(story)
    return buf.getvalue()


def _pdf_response(pdf_bytes: bytes, filename: str):
    return json_ok(
        {
            "pdf_base64": base64.b64encode(pdf_bytes).decode("ascii"),
            "filename": filename,
            "mime_type": "application/pdf",
        }
    )


def _hotel_name(request) -> str:
    hotel = getattr(request, "active_property", None)
    if hotel is not None:
        return hotel.name
    return request.tenant.name


@api_login_required
@api_role_required(*DASHBOARD)
@require_GET
def flash_print(request):
    from reports.accounting import build_daily_flash
    from reports.operations import operations_kpis

    day = timezone.localdate()
    day_s = (request.GET.get("date") or request.GET.get("day") or "").strip()
    if day_s:
        try:
            day = date.fromisoformat(day_s)
        except ValueError:
            return json_error("Invalid date.")
    hotel = getattr(request, "active_property", None)
    flash = build_daily_flash(request.tenant, day, hotel=hotel)
    kpis = operations_kpis(request.tenant, day, hotel=hotel)
    stats = flash.get("stats") or {}
    currency = request.tenant.currency or "UZS"
    rows = [
        ("OCC %", str(stats.get("occupancy_percent", "—"))),
        ("ADR", _money(stats.get("adr"), currency)),
        ("RevPAR", _money(stats.get("revpar"), currency)),
        ("Naqd tushum", _money(flash.get("revenue_cash"), currency)),
        ("Hisob (accrual)", _money(flash.get("revenue_accrual"), currency)),
        ("Xarajat", _money(flash.get("expenses_today"), currency)),
        ("Tayyor xona", str(kpis.get("ready_rooms", "—"))),
        ("Kir", str(kpis.get("dirty_rooms", "—"))),
        ("OOO", str(kpis.get("ooo_rooms", "—"))),
        ("HK vazifa", str(kpis.get("hk_tasks", "—"))),
        ("Ta’mir", str(kpis.get("maintenance_open", "—"))),
        ("Open folio", _money(kpis.get("open_folio_balance"), currency)),
    ]
    pdf = _build_statement_pdf(
        hotel_name=_hotel_name(request),
        title="Kunlik flash chek",
        subtitle=day.isoformat(),
        rows=rows,
    )
    return _pdf_response(pdf, f"flash-{day.isoformat()}.pdf")


@api_login_required
@api_role_required(*ACCOUNTING, TenantMembership.Role.MANAGER)
@require_GET
def pnl_print(request):
    from reports.accounting import build_pnl_report

    today = timezone.localdate()
    try:
        year = int(request.GET.get("year") or today.year)
        month = int(request.GET.get("month") or today.month)
    except (TypeError, ValueError):
        return json_error("Invalid year/month.")
    hotel = getattr(request, "active_property", None)
    report = build_pnl_report(
        request.tenant, year=year, month=month, hotel=hotel
    )
    currency = request.tenant.currency or "UZS"
    rows = [
        ("Daromad", _money(report.get("revenue_total"), currency)),
        ("Xarajatlar", _money(report.get("expenses"), currency)),
        ("Mehnat", _money(report.get("payroll"), currency)),
        ("Komissiya", _money(report.get("commission"), currency)),
        ("Ombor tannarx", _money(report.get("inventory_cost"), currency)),
        ("E-mehmon farq", _money(report.get("emehmon_shortfall"), currency)),
        ("Operatsion xarajat", _money(report.get("operating_costs"), currency)),
        ("Sof foyda", _money(report.get("net"), currency)),
    ]
    for item in (report.get("revenue_breakdown") or [])[:8]:
        if isinstance(item, dict):
            rows.append(
                (str(item.get("label") or "—"), _money(item.get("amount"), currency))
            )
    pdf = _build_statement_pdf(
        hotel_name=_hotel_name(request),
        title="P&L chek",
        subtitle=f"{year}-{month:02d} · {report.get('basis', 'cash')}",
        rows=rows,
    )
    return _pdf_response(pdf, f"pnl-{year}-{month:02d}.pdf")


@api_login_required
@api_role_required(*CASH)
@require_GET
def cash_shift_print(request, pk):
    from folio.models import CashShift
    from folio.services import expected_cash_in_shift

    hotel = getattr(request, "active_property", None)
    qs = CashShift.objects.filter(pk=pk, tenant=request.tenant)
    if hotel is not None:
        qs = qs.filter(hotel=hotel)
    shift = qs.first()
    if shift is None:
        return json_error("Shift not found.", status=404)
    currency = request.tenant.currency or "UZS"
    expected = ""
    try:
        if shift.is_open:
            expected = _money(expected_cash_in_shift(shift), currency)
    except Exception:
        expected = "—"
    rows = [
        ("Holat", "OCHIQ" if shift.is_open else "YOPIQ"),
        (
            "Ochilgan",
            shift.opened_at.strftime("%d.%m.%Y %H:%M") if shift.opened_at else "—",
        ),
        (
            "Yopilgan",
            shift.closed_at.strftime("%d.%m.%Y %H:%M") if shift.closed_at else "—",
        ),
        ("Boshlang‘ich", _money(shift.opening_float, currency)),
        ("Kutilgan", expected or "—"),
        (
            "Yakuniy naqd",
            _money(shift.closing_cash, currency)
            if shift.closing_cash is not None
            else "—",
        ),
        (
            "Farq",
            _money(shift.variance, currency) if shift.variance is not None else "—",
        ),
        ("Izoh", shift.notes or "—"),
    ]
    pdf = _build_statement_pdf(
        hotel_name=_hotel_name(request),
        title="Kassa smena cheki",
        subtitle=f"#{shift.pk}",
        rows=rows,
    )
    return _pdf_response(pdf, f"cash-shift-{shift.pk}.pdf")


@api_login_required
@api_role_required(*FINANCE, TenantMembership.Role.MANAGER)
@require_GET
def expense_print(request, pk):
    from finance.models import Expense

    hotel = getattr(request, "active_property", None)
    qs = Expense.objects.filter(pk=pk, tenant=request.tenant).select_related(
        "category", "vendor"
    )
    if hotel is not None:
        qs = qs.filter(hotel=hotel)
    exp = qs.first()
    if exp is None:
        return json_error("Expense not found.", status=404)
    currency = request.tenant.currency or "UZS"
    rows = [
        ("Sarlavha", exp.title),
        ("Status", exp.get_status_display() if hasattr(exp, "get_status_display") else exp.status),
        ("Summa", _money(exp.amount, currency)),
        ("Sana", exp.expense_date.isoformat() if exp.expense_date else "—"),
        ("Kategoriya", exp.category.name if exp.category_id else "—"),
        ("Yetkazuvchi", exp.vendor.name if exp.vendor_id else "—"),
        ("Izoh", getattr(exp, "notes", "") or "—"),
    ]
    pdf = _build_statement_pdf(
        hotel_name=_hotel_name(request),
        title="Xarajat cheki",
        subtitle=f"#{exp.pk}",
        rows=rows,
    )
    return _pdf_response(pdf, f"expense-{exp.pk}.pdf")


@api_login_required
@api_role_required(*FRONT_OFFICE, *FINANCE, *ACCOUNTING, TenantMembership.Role.MANAGER)
@require_GET
def commission_statement_print(request, pk):
    from bookings.models import BookingReferrer
    from bookings.commission import build_commission_report

    today = timezone.localdate()
    try:
        year = int(request.GET.get("year") or today.year)
        month = int(request.GET.get("month") or today.month)
    except (TypeError, ValueError):
        return json_error("Invalid year/month.")
    ref = BookingReferrer.objects.filter(pk=pk, tenant=request.tenant).first()
    if ref is None:
        return json_error("Referrer not found.", status=404)
    report = build_commission_report(request.tenant, year=year, month=month)
    group = next((g for g in report.get("groups") or [] if g["referrer"].pk == ref.pk), None)
    currency = request.tenant.currency or "UZS"
    rows = [("Agent", ref.name), ("Telefon", ref.phone or "—")]
    if group:
        rows.extend(
            [
                ("Bronlar", str(group.get("count", 0))),
                ("Baza", _money(group.get("base_total"), currency)),
                ("Komissiya", _money(group.get("commission_total"), currency)),
                ("To‘langan", _money(group.get("paid_total"), currency)),
                ("Qoldiq", _money(group.get("remaining"), currency)),
            ]
        )
    else:
        rows.append(("Komissiya", "0"))
    pdf = _build_statement_pdf(
        hotel_name=_hotel_name(request),
        title="Komissiya bayonnomasi",
        subtitle=f"{ref.name} · {year}-{month:02d}",
        rows=rows,
    )
    return _pdf_response(pdf, f"commission-{ref.pk}-{year}-{month:02d}.pdf")


@api_login_required
@api_role_required(*ACCOUNTING, TenantMembership.Role.MANAGER)
@require_GET
def emehmon_statement_print(request):
    """Oylik E-mehmon topshirish vedomosti — web statement bilan bir xil ma’lumot."""
    from bookings.emehmon import build_emehmon_statement

    today = timezone.localdate()
    try:
        year = int(request.GET.get("year") or today.year)
        month = int(request.GET.get("month") or today.month)
        if month < 1 or month > 12:
            raise ValueError
    except (TypeError, ValueError):
        return json_error("Invalid year/month.")
    hotel = getattr(request, "active_property", None)
    statement = build_emehmon_statement(
        request.tenant, year=year, month=month, hotel=hotel
    )
    currency = request.tenant.currency or "UZS"
    rows = [
        ("Davr", f"{year}-{month:02d}"),
        ("Yozuvlar", str(statement.get("count") or 0)),
    ]
    for row in statement.get("rows") or []:
        when = row.get("collected_at")
        when_s = when.date().isoformat() if hasattr(when, "date") else ""
        label = " · ".join(
            p
            for p in (
                str(row.get("code") or ""),
                str(row.get("guest_name") or ""),
                when_s,
            )
            if p
        )
        rows.append((label or "—", _money(row.get("amount"), currency)))
    rows.append(("Jami olingan", _money(statement.get("total_collected"), currency)))
    pdf = _build_statement_pdf(
        hotel_name=_hotel_name(request),
        title="E-mehmon bayonnomasi",
        subtitle=f"{year}-{month:02d}",
        rows=rows,
    )
    return _pdf_response(pdf, f"emehmon-{year}-{month:02d}.pdf")
