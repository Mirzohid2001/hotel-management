from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("pnl/", views.pnl_report, name="pnl"),
    path("flash/", views.daily_flash, name="flash"),
    path("flash/print/", views.daily_flash_print, name="flash_print"),
    path("audit/", views.audit_log, name="audit_log"),
    path("night-audit/", views.night_audit_run_view, name="night_audit"),
    path("export/payments.csv", views.export_payments_csv, name="export_payments"),
    path("export/pnl.csv", views.export_pnl_csv, name="export_pnl"),
    path("export/ar.csv", views.export_ar_csv, name="export_ar"),
]
