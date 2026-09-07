from django.contrib import admin

from .models import NightAuditRun


@admin.register(NightAuditRun)
class NightAuditRunAdmin(admin.ModelAdmin):
    list_display = (
        "audit_date",
        "tenant",
        "posted_room_charges",
        "occupancy_percent",
        "revenue",
    )
    list_filter = ("tenant",)
