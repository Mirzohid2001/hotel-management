from django.contrib import admin

from .models import MaintenanceTicket


@admin.register(MaintenanceTicket)
class MaintenanceTicketAdmin(admin.ModelAdmin):
    list_display = ("title", "room", "priority", "status", "tenant")
    list_filter = ("status", "priority", "tenant")
