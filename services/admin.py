from django.contrib import admin

from .models import ServiceItem, ServiceOrder


@admin.register(ServiceItem)
class ServiceItemAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "unit_price", "tenant", "is_active")
    list_filter = ("tenant", "is_active")


@admin.register(ServiceOrder)
class ServiceOrderAdmin(admin.ModelAdmin):
    list_display = ("service", "reservation", "quantity", "amount", "tenant")
