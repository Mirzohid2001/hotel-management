from django.contrib import admin

from .models import (
    CashShift,
    CashShiftMovement,
    CompanyInvoice,
    CompanyPayment,
    Folio,
    FolioCharge,
    GuestPayment,
)


class ChargeInline(admin.TabularInline):
    model = FolioCharge
    extra = 0
    fields = ("charge_type", "description", "quantity", "unit_price", "amount", "is_void", "created_at")
    readonly_fields = ("amount", "created_at")
    show_change_link = True


class PaymentInline(admin.TabularInline):
    model = GuestPayment
    extra = 0
    fields = ("method", "amount", "kind", "is_void", "created_at", "note")
    readonly_fields = ("created_at",)
    show_change_link = True


@admin.register(Folio)
class FolioAdmin(admin.ModelAdmin):
    list_display = ("reservation", "tenant", "is_open", "opened_at")
    list_filter = ("is_open", "tenant")
    search_fields = ("reservation__code", "reservation__guest__first_name", "reservation__guest__last_name")
    autocomplete_fields = ("reservation", "tenant")
    inlines = [ChargeInline, PaymentInline]
    list_select_related = ("reservation", "tenant")
    date_hierarchy = "opened_at"


@admin.register(CashShift)
class CashShiftAdmin(admin.ModelAdmin):
    list_display = ("tenant", "hotel", "opened_by", "opened_at", "closed_at", "opening_float", "variance")
    list_filter = ("tenant", "hotel")
    search_fields = ("notes", "opened_by__username")
    autocomplete_fields = ("tenant", "hotel", "opened_by", "closed_by")
    date_hierarchy = "opened_at"
    list_select_related = ("tenant", "hotel", "opened_by")


@admin.register(CashShiftMovement)
class CashShiftMovementAdmin(admin.ModelAdmin):
    list_display = ("shift", "kind", "amount", "note", "created_by", "created_at", "tenant")
    list_filter = ("kind", "tenant")
    search_fields = ("note",)
    autocomplete_fields = ("shift", "tenant", "created_by")
    date_hierarchy = "created_at"


@admin.register(CompanyInvoice)
class CompanyInvoiceAdmin(admin.ModelAdmin):
    list_display = ("code", "company", "status", "due_date", "tenant", "issued_at")
    list_filter = ("status", "tenant")
    search_fields = ("code", "company__name")
    autocomplete_fields = ("company", "tenant")
    date_hierarchy = "issued_at"


@admin.register(CompanyPayment)
class CompanyPaymentAdmin(admin.ModelAdmin):
    list_display = ("invoice", "method", "amount", "is_void", "created_at")
    list_filter = ("method", "is_void")
    search_fields = ("invoice__code", "note")
    autocomplete_fields = ("invoice",)
    date_hierarchy = "created_at"
