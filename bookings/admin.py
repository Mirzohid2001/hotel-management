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


@admin.register(ReferrerCommissionPayment)
class ReferrerCommissionPaymentAdmin(admin.ModelAdmin):
    list_display = ("referrer", "tenant", "year", "month", "amount", "paid_on", "method")
    list_filter = ("tenant", "year", "month", "method")
    search_fields = ("referrer__name", "note")


@admin.register(ReservationGroup)
class ReservationGroupAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "tenant", "hotel", "check_in", "check_out")
    list_filter = ("tenant",)
    search_fields = ("code", "name")


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "tenant",
        "guest",
        "room",
        "referrer",
        "commission_percent",
        "group",
        "check_in",
        "check_out",
        "status",
    )
    list_filter = ("status", "tenant", "source")
    search_fields = ("code", "guest__first_name", "guest__last_name", "referrer__name")
    inlines = [ChangeLogInline]


@admin.register(Stay)
class StayAdmin(admin.ModelAdmin):
    list_display = ("reservation", "actual_check_in", "actual_check_out")
