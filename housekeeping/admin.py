from django.contrib import admin

from .models import HousekeepingTask, RoomStatusLog


@admin.register(HousekeepingTask)
class HousekeepingTaskAdmin(admin.ModelAdmin):
    list_display = ("room", "title", "status", "assigned_to", "tenant")
    list_filter = ("status", "tenant")


@admin.register(RoomStatusLog)
class RoomStatusLogAdmin(admin.ModelAdmin):
    list_display = ("room", "old_status", "new_status", "user", "created_at")
    list_filter = ("tenant",)
