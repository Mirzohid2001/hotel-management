from django.contrib import admin

from .models import ApiToken


@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "tenant", "label", "created_at", "last_used_at", "revoked_at")
    list_filter = ("label", "tenant")
    search_fields = ("user__username", "key")
    readonly_fields = ("key", "created_at", "last_used_at")
