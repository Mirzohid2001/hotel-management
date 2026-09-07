from decimal import Decimal

from django.conf import settings
from django.db import models

from core.currency import CURRENCY_CHOICES
from core.models import TenantOwnedModel


class ServiceItem(TenantOwnedModel):
    name = models.CharField(max_length=200)
    code = models.SlugField(max_length=40)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="UZS")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "code")

    def __str__(self) -> str:
        return self.name


class ServiceOrder(TenantOwnedModel):
    reservation = models.ForeignKey(
        "bookings.Reservation", on_delete=models.CASCADE, related_name="service_orders"
    )
    service = models.ForeignKey(ServiceItem, on_delete=models.PROTECT, related_name="orders")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1"))
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_orders",
    )
    folio_charge = models.ForeignKey(
        "folio.FolioCharge",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_orders",
    )

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        self.amount = (self.quantity or Decimal("0")) * (self.unit_price or Decimal("0"))
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.service} × {self.quantity}"
