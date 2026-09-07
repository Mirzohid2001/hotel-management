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


class PaymentInline(admin.TabularInline):
    model = GuestPayment
    extra = 0


@admin.register(Folio)
class FolioAdmin(admin.ModelAdmin):
    list_display = ("reservation", "tenant", "is_open", "opened_at")
    list_filter = ("is_open", "tenant")
    inlines = [ChargeInline, PaymentInline]


@admin.register(CashShift)
class CashShiftAdmin(admin.ModelAdmin):
    list_display = ("tenant", "opened_by", "opened_at", "closed_at", "opening_float", "variance")
    list_filter = ("tenant",)
    search_fields = ("notes",)


@admin.register(CashShiftMovement)
class CashShiftMovementAdmin(admin.ModelAdmin):
    list_display = ("shift", "kind", "amount", "note", "created_by", "created_at", "tenant")
    list_filter = ("kind", "tenant")
    search_fields = ("note",)


@admin.register(CompanyInvoice)
class CompanyInvoiceAdmin(admin.ModelAdmin):
    list_display = ("code", "company", "status", "due_date", "tenant", "issued_at")
    list_filter = ("status", "tenant")


@admin.register(CompanyPayment)
class CompanyPaymentAdmin(admin.ModelAdmin):
    list_display = ("invoice", "method", "amount", "is_void", "created_at")
