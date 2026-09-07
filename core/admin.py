from django.contrib import admin

from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "tenant", "user", "action", "model", "object_id")
    list_filter = ("action", "tenant")
    search_fields = ("action", "model", "object_id", "user__username")
    readonly_fields = ("created_at",)
