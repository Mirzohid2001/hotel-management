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


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "phone", "is_active")


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("title", "amount", "expense_date", "status", "tenant")
    list_filter = ("status", "tenant")


@admin.register(ProfitPartner)
class ProfitPartnerAdmin(admin.ModelAdmin):
    list_display = ("name", "share_percent", "is_active", "tenant")
    list_filter = ("is_active", "tenant")


@admin.register(ProfitPeriod)
class ProfitPeriodAdmin(admin.ModelAdmin):
    list_display = ("started_on", "ended_on", "net_snapshot", "tenant")
    list_filter = ("tenant",)


@admin.register(ProfitWithdrawal)
class ProfitWithdrawalAdmin(admin.ModelAdmin):
    list_display = ("partner", "amount", "paid_on", "period", "tenant")
    list_filter = ("tenant", "payment_method")
