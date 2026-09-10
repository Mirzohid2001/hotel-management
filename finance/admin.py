from django.contrib import admin

from .models import (
    Expense,
    ExpenseCategory,
    ProfitPartner,
    ProfitPeriod,
    ProfitWithdrawal,
    Vendor,
)


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "is_active")
    list_filter = ("tenant", "is_active")
    search_fields = ("name",)
    autocomplete_fields = ("tenant",)


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "phone", "is_active")
    list_filter = ("tenant", "is_active")
    search_fields = ("name", "phone")
    autocomplete_fields = ("tenant",)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "hotel",
        "category",
        "funding",
        "amount",
        "expense_date",
        "status",
        "tenant",
    )
    list_filter = ("status", "funding", "tenant", "hotel", "category")
    search_fields = ("title", "notes")
    autocomplete_fields = ("tenant", "hotel", "category", "vendor", "maintenance_ticket")
    date_hierarchy = "expense_date"
    list_select_related = ("tenant", "hotel", "category", "vendor")


@admin.register(ProfitPartner)
class ProfitPartnerAdmin(admin.ModelAdmin):
    list_display = ("name", "share_percent", "is_active", "tenant")
    list_filter = ("is_active", "tenant")
    search_fields = ("name",)
    autocomplete_fields = ("tenant",)


@admin.register(ProfitPeriod)
class ProfitPeriodAdmin(admin.ModelAdmin):
    list_display = ("started_on", "ended_on", "net_snapshot", "tenant")
    list_filter = ("tenant",)
    search_fields = ("tenant__name",)
    autocomplete_fields = ("tenant",)
    date_hierarchy = "started_on"


@admin.register(ProfitWithdrawal)
class ProfitWithdrawalAdmin(admin.ModelAdmin):
    list_display = ("partner", "amount", "paid_on", "period", "tenant")
    list_filter = ("tenant", "payment_method")
    search_fields = ("partner__name", "note")
    autocomplete_fields = ("partner", "period", "tenant")
    date_hierarchy = "paid_on"
