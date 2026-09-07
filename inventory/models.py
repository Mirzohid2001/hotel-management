from datetime import timedelta
from decimal import Decimal

from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.db import models
from django.utils import timezone

from core.currency import CURRENCY_CHOICES
from core.models import TenantOwnedModel


class StockItem(TenantOwnedModel):
    class Unit(models.TextChoices):
        DONA = "dona", _("Dona")
        KG = "kg", _("Kg")
        G = "g", _("Gramm")
        L = "l", _("Litr")
        ML = "ml", _("Ml")
        QUTI = "quti", _("Quti")
        PAKET = "paket", _("Paket")
        JUFT = "juft", _("Juft")
        METR = "m", _("Metr")
        PCS = "pcs", _("Dona (pcs)")  # eski yozuvlar uchun

    class ExpiryStatus:
        NONE = "none"
        OK = "ok"
        SOON = "soon"
        EXPIRED = "expired"

    hotel = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="stock_items",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=200)
    sku = models.SlugField(max_length=40)
    unit = models.CharField(
        max_length=32,
        choices=Unit.choices,
        default=Unit.DONA,
    )
    quantity_on_hand = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    reorder_level = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        help_text=_("Qoldiq shu qiymatga teng yoki past bo‘lsa ogohlantirish."),
    )
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    sell_price = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="UZS")
    expiry_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Yaroqlilik muddati"),
        help_text=_("Bo‘sh qoldirilsa muddat kuzatilmaydi."),
    )
    expiry_alert_days = models.PositiveSmallIntegerField(
        default=7,
        verbose_name=_("Ogohlantirish (kun)"),
        help_text=_("Muddatdan shuncha kun oldin «yaqin» deb ogohlantiriladi."),
    )
    is_minibar = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "hotel", "sku")

    def __str__(self) -> str:
        return self.name

    def expiry_status(self, on_date=None) -> str:
        """none | ok | soon | expired — faqat omborda qoldiq bo‘lsa."""
        if not self.expiry_date:
            return self.ExpiryStatus.NONE
        if (self.quantity_on_hand or Decimal("0")) <= 0:
            return self.ExpiryStatus.NONE
        today = on_date or timezone.localdate()
        if self.expiry_date < today:
            return self.ExpiryStatus.EXPIRED
        alert_days = int(self.expiry_alert_days if self.expiry_alert_days is not None else 7)
        if self.expiry_date <= today + timedelta(days=alert_days):
            return self.ExpiryStatus.SOON
        return self.ExpiryStatus.OK

    @property
    def days_until_expiry(self) -> int | None:
        if not self.expiry_date:
            return None
        return (self.expiry_date - timezone.localdate()).days


class StockMovement(TenantOwnedModel):
    class MovementType(models.TextChoices):
        IN = "in", _("Kirim")
        OUT = "out", _("Chiqim")
        ADJUST = "adjust", _("Tuzatish")

    item = models.ForeignKey(StockItem, on_delete=models.CASCADE, related_name="movements")
    movement_type = models.CharField(max_length=16, choices=MovementType.choices)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )

    class Meta:
        ordering = ["-created_at"]


class MinibarSale(TenantOwnedModel):
    reservation = models.ForeignKey(
        "bookings.Reservation", on_delete=models.CASCADE, related_name="minibar_sales"
    )
    item = models.ForeignKey(StockItem, on_delete=models.PROTECT, related_name="minibar_sales")
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("1"))
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    folio_charge = models.ForeignKey(
        "folio.FolioCharge",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="minibar_sales",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="minibar_sales",
    )

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        self.amount = (self.quantity or Decimal("0")) * (self.unit_price or Decimal("0"))
        super().save(*args, **kwargs)
