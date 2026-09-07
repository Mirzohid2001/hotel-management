from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .forms import CompanyAdminForm
from .models import Company, Guest, GuestDocument, GuestNote


class GuestDocumentInline(admin.TabularInline):
    model = GuestDocument
    extra = 0


class GuestNoteInline(admin.TabularInline):
    model = GuestNote
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    form = CompanyAdminForm
    list_display = ("name", "tenant", "inn", "phone", "is_active")
    list_filter = ("tenant", "is_active")
    search_fields = ("name", "inn", "phone")
    autocomplete_fields = ("tenant",)
    ordering = ("name",)
    fieldsets = (
        (
            _("Asosiy"),
            {
                "description": _(
                    "Tenant — qaysi mehmonxonaga tegishli ekanini bildiradi (majburiy). "
                    "Bir mehmonxonada kompaniya nomi takrorlanmasligi kerak."
                ),
                "fields": ("tenant", "name", "inn", "phone", "email", "is_active"),
            },
        ),
        (
            _("Manzil va izoh"),
            {"fields": ("address", "notes")},
        ),
        (
            _("To‘lov shartlari"),
            {
                "description": _(
                    "Bo‘sh qoldirilsa: to‘lov muddati 30 kun, kredit limiti 0."
                ),
                "fields": ("payment_terms_days", "credit_limit"),
            },
        ),
    )


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "phone", "is_vip", "is_blacklisted", "tenant")
    list_filter = ("tenant", "is_vip", "is_blacklisted")
    search_fields = ("first_name", "last_name", "phone", "email")
    inlines = [GuestDocumentInline, GuestNoteInline]


@admin.register(GuestDocument)
class GuestDocumentAdmin(admin.ModelAdmin):
    list_display = ("guest", "doc_type", "number", "expiry_date", "tenant")
    list_filter = ("doc_type", "tenant")
