from django.contrib import admin

from widget.admin import WidgetConfigInline

from .models import Floor, Property, PropertySettings, RatePlan, Room, RoomType, SeasonRate


class PropertySettingsInline(admin.StackedInline):
    model = PropertySettings
    extra = 0


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("name", "branch_code", "tenant", "city", "is_active")
    list_filter = ("tenant", "is_active")
    search_fields = ("name", "city", "branch_code")
    inlines = [PropertySettingsInline, WidgetConfigInline]


@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ("property", "number", "name", "tenant")
    list_filter = ("tenant", "property")


@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "property", "base_price", "is_active")
    list_filter = ("tenant", "property", "is_active")
    search_fields = ("name", "code")


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("number", "property", "room_type", "status", "is_active")
    list_filter = ("tenant", "property", "status", "is_active")
    search_fields = ("number",)


@admin.register(RatePlan)
class RatePlanAdmin(admin.ModelAdmin):
    list_display = ("name", "property", "room_type", "price", "is_default", "is_active")
    list_filter = ("tenant", "property", "is_active")


@admin.register(SeasonRate)
class SeasonRateAdmin(admin.ModelAdmin):
    list_display = ("name", "rate_plan", "date_from", "date_to", "price")
    list_filter = ("tenant",)
