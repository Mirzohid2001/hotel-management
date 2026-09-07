from django.contrib import admin

from .models import Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "price_monthly", "price_yearly", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "plan",
        "status",
        "billing_period",
        "period_start",
        "period_end",
    )
    list_filter = ("status", "plan", "billing_period")
    search_fields = ("tenant__name", "admin_notes")
    autocomplete_fields = ("tenant", "plan")
    readonly_fields = ("created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        obj.sync_status_with_dates()
        super().save_model(request, obj, form, change)
