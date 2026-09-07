from django.contrib import admin

from .models import MinibarSale, StockItem, StockMovement


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sku",
        "quantity_on_hand",
        "expiry_date",
        "expiry_alert_days",
        "is_minibar",
        "tenant",
    )
    list_filter = ("is_minibar", "tenant", "expiry_date")
    search_fields = ("name", "sku")


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("item", "movement_type", "quantity", "created_at")


@admin.register(MinibarSale)
class MinibarSaleAdmin(admin.ModelAdmin):
    list_display = ("item", "reservation", "quantity", "amount")
