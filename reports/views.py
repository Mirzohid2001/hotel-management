import csv
from datetime import date

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dates import MONTHS
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.models import ActivityLog
from core.mixins import feature_required, role_required
from core.roles import ACCOUNTING, AUDIT, DASHBOARD
from folio.city_ledger import ar_aging
from folio.models import GuestPayment

from properties.models import Property

from .accounting import (
    build_daily_flash,
    build_pnl_report,
    guest_ar_summary,
)
from .models import NightAuditRun
from .night_audit import audit_blockers, build_cod_checklist, run_night_audit
from .chart_data import dashboard_charts, flash_charts, pnl_charts
from .operations import dashboard_insights, operations_kpis, revenue_trend, room_status_summary
from .services import (
    adr_revpar,
    arrivals_on,
    departures_on,
    in_house_on,
    pnl_lite,
    revenue_on,
)


@role_required(*DASHBOARD)
def dashboard(request):
    tenant = request.tenant
    hotel = getattr(request, "active_property", None)
    day = timezone.localdate()
    stats = adr_revpar(tenant, day, hotel=hotel)
    pnl = pnl_lite(tenant, day.year, day.month) if tenant.has_feature("pnl") else None
    latest_audit = None
    if hotel:
        latest_audit = (
            NightAuditRun.objects.filter(tenant=tenant, hotel=hotel).order_by("-audit_date").first()
        )
    today_locked = False
    if hotel:
        today_locked = NightAuditRun.objects.filter(
            tenant=tenant, hotel=hotel, audit_date=day
        ).exists()
    elif tenant_properties_count := Property.objects.filter(tenant=tenant, is_active=True).count():
        from reports.day_lock import is_day_locked

        today_locked = is_day_locked(tenant, day)
    cod_preview = None
    audit_blocker_list = []
    if tenant.has_feature("night_audit") and hotel and not today_locked:
        cod_preview = build_cod_checklist(tenant, day, hotel=hotel)
        audit_blocker_list = audit_blockers(tenant, day, hotel=hotel)
    ops = operations_kpis(tenant, day, hotel=hotel)
    insights = dashboard_insights(tenant, day, hotel=hotel)
    chart_data = dashboard_charts(tenant, day, hotel=hotel, currency=tenant.currency)
    return render(
        request,
        "reports/dashboard.html",
        {
            "tenant": tenant,
            "subscription": tenant.get_active_subscription(),
            "membership": request.membership,
            "day": day,
            "stats": stats,
            "insights": insights,
            "ops": ops,
            "room_status": room_status_summary(tenant, hotel=hotel),
            "revenue_trend": revenue_trend(tenant, day, hotel=hotel),
            "arrivals": arrivals_on(tenant, day, hotel=hotel),
            "departures": departures_on(tenant, day, hotel=hotel),
            "in_house": in_house_on(tenant, day, hotel=hotel),
            "revenue_today": revenue_on(tenant, day, hotel=hotel),
            "pnl": pnl,
            "latest_audit": latest_audit,
            "today_locked": today_locked,
            "cod_preview": cod_preview,
            "audit_blockers": audit_blocker_list,
            "audit_blocked": bool(audit_blocker_list),
            "can_night_audit": tenant.has_feature("night_audit") and hotel is not None,
            "can_csv": tenant.has_feature("csv_export"),
            "can_pnl": tenant.has_feature("pnl"),
            "active_hotel": hotel,
            "chart_data": chart_data,
        },
    )


@feature_required("pnl")
@role_required(*ACCOUNTING)
def pnl_report(request):
    tenant = request.tenant
    hotel = getattr(request, "active_property", None)
    today = timezone.localdate()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))
    basis = request.GET.get("basis", "cash")
    report = build_pnl_report(tenant, year, month, basis=basis, hotel=hotel)
    months = [(i, MONTHS[i]) for i in range(1, 13)]
    chart_data = pnl_charts(report, currency=tenant.currency)
    return render(
        request,
        "reports/pnl.html",
        {
            "report": report,
            "year": year,
            "month": month,
            "basis": basis,
            "months": months,
            "can_csv": tenant.has_feature("csv_export"),
            "active_hotel": hotel,
            "chart_data": chart_data,
        },
    )


@feature_required("pnl")
@role_required(*ACCOUNTING)
def daily_flash(request):
    tenant = request.tenant
    hotel = getattr(request, "active_property", None)
    day_str = request.GET.get("day")
    if day_str:
        try:
            day = date.fromisoformat(day_str)
        except ValueError:
            day = timezone.localdate()
    else:
        day = timezone.localdate()
    flash = build_daily_flash(tenant, day, hotel=hotel)
    chart_data = flash_charts(flash, currency=tenant.currency)
    return render(
        request,
        "reports/flash.html",
        {"flash": flash, "day": day, "active_hotel": hotel, "chart_data": chart_data},
    )


@feature_required("pnl")
@role_required(*ACCOUNTING)
def daily_flash_print(request):
    """Kunlik hisobot cheki — chop etish / PDF (brauzer)."""
    tenant = request.tenant
    hotel = getattr(request, "active_property", None)
    day_str = request.GET.get("day")
    if day_str:
        try:
            day = date.fromisoformat(day_str)
        except ValueError:
            day = timezone.localdate()
    else:
        day = timezone.localdate()
    flash = build_daily_flash(tenant, day, hotel=hotel)
    return render(
        request,
        "reports/flash_print.html",
        {
            "flash": flash,
            "day": day,
            "active_hotel": hotel,
            "tenant": tenant,
            "printed_at": timezone.localtime(),
            "printed_by": request.user.get_full_name() or request.user.username,
        },
    )


@feature_required("reports_advanced")
@role_required(*ACCOUNTING)
def audit_log(request):
    logs = ActivityLog.objects.filter(tenant=request.tenant).select_related("user")[:200]
    return render(request, "reports/audit_log.html", {"logs": logs})


@feature_required("night_audit")
@role_required(*AUDIT)
@require_POST
def night_audit_run_view(request):
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        messages.error(request, _("Kun yopish uchun filial tanlang (barcha filiallar rejimida emas)."))
        return redirect("reports:dashboard")
    try:
        run = run_night_audit(request.tenant, request.user, hotel=hotel)
        messages.success(
            request,
            _(
                "%(hotel)s · kun yopish %(day)s: %(posted)s xona · %(noshow)s kelmagan · "
                "%(overdue)s qarz · %(dirty)s kir."
            )
            % {
                "hotel": hotel.name,
                "day": run.audit_date,
                "posted": run.posted_room_charges,
                "noshow": run.no_shows_marked,
                "overdue": run.overdue_folios,
                "dirty": run.dirty_rooms,
            },
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("reports:dashboard")


@feature_required("csv_export")
@role_required(*ACCOUNTING)
def export_payments_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="payments.csv"'
    writer = csv.writer(response)
    writer.writerow(["date", "reservation", "method", "kind", "amount"])
    qs = (
        GuestPayment.objects.filter(tenant=request.tenant, is_void=False)
        .select_related("folio__reservation")
        .order_by("-created_at")[:2000]
    )
    for p in qs:
        writer.writerow(
            [
                p.created_at.date().isoformat(),
                p.folio.reservation.code,
                p.method,
                p.kind,
                str(p.amount),
            ]
        )
    return response


@feature_required("csv_export")
@role_required(*ACCOUNTING)
def export_pnl_csv(request):
    today = timezone.localdate()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))
    basis = request.GET.get("basis", "cash")
    hotel = getattr(request, "active_property", None)
    report = build_pnl_report(request.tenant, year, month, basis=basis, hotel=hotel)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="pnl-{year}-{month:02d}-{basis}.csv"'
    writer = csv.writer(response)
    writer.writerow(["section", "label", "amount"])
    writer.writerow(["revenue", "total", str(report["revenue_total"])])
    for row in report["revenue_breakdown"]:
        label = row.get("label", row.get("key", ""))
        writer.writerow(["revenue", label, str(row["amount"])])
    writer.writerow(["expense", "total", str(report["expenses_total"])])
    for row in report["expenses_breakdown"]:
        writer.writerow(["expense", row["label"], str(row["amount"])])
    writer.writerow(["payroll", "total", str(report["payroll"])])
    writer.writerow(["advances", "total", str(report["advances"])])
    writer.writerow(["commission", "total", str(report["commission"])])
    writer.writerow(["inventory", "total", str(report["inventory_cost"])])
    writer.writerow(["emehmon_shortfall", "total", str(report.get("emehmon_shortfall") or 0)])
    writer.writerow(["operating", "total", str(report["operating_costs"])])
    writer.writerow(["net", "net", str(report["net"])])
    return response


@feature_required("csv_export")
@role_required(*ACCOUNTING)
def export_ar_csv(request):
    tenant = request.tenant
    aging = ar_aging(tenant)
    guest_ar = guest_ar_summary(tenant)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="ar-aging.csv"'
    writer = csv.writer(response)
    writer.writerow(["type", "bucket", "code", "name", "balance"])
    for bucket in aging["buckets"].values():
        for inv in bucket["invoices"]:
            writer.writerow(
                [
                    "company",
                    bucket["label"],
                    inv.code,
                    inv.company.name,
                    str(inv.balance),
                ]
            )
    for row in guest_ar["rows"]:
        writer.writerow(["guest", "open_folio", row["code"], row["guest"], str(row["balance"])])
    writer.writerow(["", "guest_total", "", "", str(guest_ar["total"])])
    writer.writerow(["", "company_total", "", "", str(aging["grand_total"])])
    return response
