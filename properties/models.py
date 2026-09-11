from datetime import time
from decimal import Decimal

from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.db import models

from core.currency import CURRENCY_CHOICES
from core.models import TenantOwnedModel


class Property(TenantOwnedModel):
    name = models.CharField(max_length=200)
    branch_code = models.SlugField(
        max_length=32,
        blank=True,
        verbose_name=_("Filial kodi"),
        help_text=_("Bron kodi va widget URL uchun: tsh, chilanzar"),
    )
    address = models.CharField(max_length=500, blank=True)
    city = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "properties"
        ordering = ["name"]
        unique_together = ("tenant", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "branch_code"),
                condition=~models.Q(branch_code=""),
                name="uniq_tenant_branch_code",
            )
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.branch_code:
            base = slugify(self.name) or "filial"
            code = base[:32]
            n = 1
            while (
                Property.objects.filter(tenant_id=self.tenant_id, branch_code=code)
                .exclude(pk=self.pk)
                .exists()
            ):
                n += 1
                code = f"{base[:28]}-{n}"
            self.branch_code = code
        super().save(*args, **kwargs)

    @property
    def display_label(self) -> str:
        if self.branch_code:
            return f"{self.name} ({self.branch_code.upper()})"
        return self.name


class PropertySettings(TenantOwnedModel):
    property = models.OneToOneField(
        Property, on_delete=models.CASCADE, related_name="settings"
    )
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))
    early_checkin_fee = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    late_checkout_fee = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    emehmon_fee = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("9000"),
        help_text="E-mehmon: 1 mehmon × 1 kecha tarifi (odatda 9000 so‘m).",
    )
    cancel_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))
    no_show_fee_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0"),
        help_text=_("Eski sozlama; kelmaganda jarima yozilmaydi — to‘lov qaytariladi."),
    )
    checkin_time = models.TimeField(default=time(14, 0))
    checkout_time = models.TimeField(default=time(12, 0))
    require_id_on_checkin = models.BooleanField(
        default=True,
        help_text="Block check-in when guest has no passport/ID document.",
    )

    class Meta:
        verbose_name_plural = "property settings"

    def __str__(self) -> str:
        return f"Settings · {self.property}"


class Floor(TenantOwnedModel):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="floors")
    number = models.IntegerField()
    name = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["number"]
        unique_together = ("property", "number")

    def __str__(self) -> str:
        if self.name:
            return self.name
        return f"{self.number}"

    def clean(self):
        if self.property_id and self.tenant_id and self.property.tenant_id != self.tenant_id:
            raise ValidationError(_("Qavat mehmonxonasi mos kelishi kerak."))


class RoomType(TenantOwnedModel):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="room_types")
    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=40)
    capacity_adults = models.PositiveSmallIntegerField(default=2)
    capacity_children = models.PositiveSmallIntegerField(default=0)
    base_price = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="UZS")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("property", "code")

    def __str__(self) -> str:
        return self.name


class Room(TenantOwnedModel):
    class Status(models.TextChoices):
        READY = "ready", _("Tayyor")
        DIRTY = "dirty", _("Kir")
        CLEANING = "cleaning", _("Tozalanmoqda")
        INSPECTED = "inspected", _("Tekshirilgan")
        OUT_OF_ORDER = "out_of_order", _("Nosoz")

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="rooms")
    room_type = models.ForeignKey(RoomType, on_delete=models.PROTECT, related_name="rooms")
    floor = models.ForeignKey(
        Floor, on_delete=models.SET_NULL, null=True, blank=True, related_name="rooms"
    )
    number = models.CharField(max_length=32)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.READY)
    notes = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["number"]
        unique_together = ("property", "number")

    def __str__(self) -> str:
        return self.number

    def clean(self):
        if self.room_type_id and self.property_id and self.room_type.property_id != self.property_id:
            raise ValidationError(_("Xona turi shu mehmonxonaga tegishli bo‘lishi kerak."))
        if self.floor_id and self.property_id and self.floor.property_id != self.property_id:
            raise ValidationError(_("Qavat shu mehmonxonaga tegishli bo‘lishi kerak."))


class RatePlan(TenantOwnedModel):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="rate_plans")
    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=40)
    room_type = models.ForeignKey(RoomType, on_delete=models.CASCADE, related_name="rate_plans")
    price = models.DecimalField(max_digits=14, decimal_places=2)
    extra_adult_price = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="UZS")
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("property", "code")

    def __str__(self) -> str:
        return f"{self.name} ({self.price})"


class SeasonRate(TenantOwnedModel):
    rate_plan = models.ForeignKey(RatePlan, on_delete=models.CASCADE, related_name="seasons")
    name = models.CharField(max_length=120)
    date_from = models.DateField()
    date_to = models.DateField()
    price = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        ordering = ["date_from"]

    def __str__(self) -> str:
        return f"{self.name}: {self.date_from}–{self.date_to}"

    def clean(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValidationError(_("Boshlanish sanasi tugashdan oldin bo‘lishi kerak."))
