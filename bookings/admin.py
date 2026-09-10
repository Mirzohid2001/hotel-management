from django.contrib import admin

from .models import (
    BookingReferrer,
    ReferrerCommissionPayment,
    Reservation,
    ReservationChangeLog,
    ReservationGroup,
    Stay,
)


class ChangeLogInline(admin.TabularInline):
    model = ReservationChangeLog
    extra = 0
    readonly_fields = ("field", "old_value", "new_value", "reason", "user", "created_at")
    can_delete = False


@admin.register(BookingReferrer)
class BookingReferrerAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "phone", "default_commission_percent", "is_active")
    list_filter = ("tenant", "is_active")
    search_fields = ("name", "phone", "notes")


@admin.register(ReferrerCommissionPayment)
class ReferrerCommissionPaymentAdmin(admin.ModelAdmin):
    list_display = ("referrer", "tenant", "year", "month", "amount", "paid_on", "method")
    list_filter = ("tenant", "year", "month", "method")
    search_fields = ("referrer__name", "note")
    autocomplete_fields = ("referrer", "tenant")
    date_hierarchy = "paid_on"


@admin.register(ReservationGroup)
class ReservationGroupAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "tenant", "hotel", "check_in", "check_out")
    list_filter = ("tenant", "hotel")
    search_fields = ("code", "name")
    autocomplete_fields = ("tenant", "hotel")
    date_hierarchy = "check_in"


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "tenant",
        "hotel",
        "guest",
        "room",
        "status",
        "check_in",
        "check_out",
        "referrer",
        "commission_percent",
    )
    list_filter = ("status", "tenant", "hotel", "source")
    search_fields = ("code", "guest__first_name", "guest__last_name", "referrer__name", "room__number")
    autocomplete_fields = ("tenant", "hotel", "guest", "room", "referrer", "group")
    date_hierarchy = "check_in"
    inlines = [ChangeLogInline]
    list_select_related = ("tenant", "hotel", "guest", "room", "referrer")


@admin.register(Stay)
class StayAdmin(admin.ModelAdmin):
    list_display = ("reservation", "actual_check_in", "actual_check_out")
    search_fields = ("reservation__code",)
    autocomplete_fields = ("reservation",)
    list_select_related = ("reservation",)
