from django.conf import settings
from django.db import models
from django.utils.text import slugify

from django.utils.translation import gettext_lazy as _

from core.currency import CURRENCY_CHOICES


class Tenant(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    timezone = models.CharField(max_length=64, default="Asia/Tashkent")
    currency = models.CharField(
        max_length=8,
        choices=CURRENCY_CHOICES,
        default="UZS",
        help_text=_("Bazaviy valyuta — hisobotlar, P&L, balans shu valyutada."),
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "hotel"
            slug = base
            n = 1
            while Tenant.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f"{base}-{n}"
            self.slug = slug
        super().save(*args, **kwargs)

    def get_active_subscription(self):
        from subscriptions.models import Subscription

        return (
            Subscription.objects.filter(tenant=self, status=Subscription.Status.ACTIVE)
            .select_related("plan")
            .order_by("-period_end")
            .first()
        )

    def has_feature(self, feature: str) -> bool:
        sub = self.get_active_subscription()
        if not sub or not sub.is_currently_valid():
            return False
        features = sub.plan.limits.get("features", [])
        return feature in features

    def check_limit(self, name: str, current: int) -> bool:
        """Return True if current count is within plan limit (None/unlimited = ok)."""
        sub = self.get_active_subscription()
        if not sub or not sub.is_currently_valid():
            return False
        limit = sub.plan.limits.get(name)
        if limit is None:
            return True
        return current < limit


class TenantMembership(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", _("Admin")
        MANAGER = "manager", _("Menejer")
        RECEPTIONIST = "receptionist", _("Qabulxona")
        HOUSEKEEPER = "housekeeper", _("Tozalash")
        ACCOUNTANT = "accountant", _("Hisobchi")
        HR = "hr", _("Kadrlar")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.MANAGER)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "tenant")
        ordering = ["tenant__name", "user__username"]

    def __str__(self) -> str:
        return f"{self.user} @ {self.tenant} ({self.role})"

    def assigned_property_ids(self) -> list[int]:
        return list(self.property_assignments.values_list("property_id", flat=True))

    def has_property_restrictions(self) -> bool:
        return bool(self.assigned_property_ids())


class MembershipProperty(models.Model):
    """Xodim qaysi filiallarda ishlashi (bo‘sh = barcha filiallar)."""

    membership = models.ForeignKey(
        TenantMembership,
        on_delete=models.CASCADE,
        related_name="property_assignments",
    )
    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="staff_assignments",
    )

    class Meta:
        unique_together = ("membership", "property")
        verbose_name = _("Filial biriktirish")
        verbose_name_plural = _("Filial biriktirishlar")

    def __str__(self) -> str:
        return f"{self.membership.user} → {self.property.name}"


class ExchangeRate(models.Model):
    """Valyuta kursi: 1 currency = rate × base_currency (masalan 1 USD = 12700 UZS)."""

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="exchange_rates"
    )
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    base_currency = models.CharField(
        max_length=3, choices=CURRENCY_CHOICES, default="UZS"
    )
    rate = models.DecimalField(max_digits=18, decimal_places=6)
    effective_on = models.DateField()
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-effective_on", "currency"]
        unique_together = ("tenant", "currency", "base_currency", "effective_on")
        verbose_name = _("Valyuta kursi")
        verbose_name_plural = _("Valyuta kurslari")

    def __str__(self) -> str:
        return f"1 {self.currency} = {self.rate} {self.base_currency} ({self.effective_on})"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.currency == self.base_currency:
            raise ValidationError(_("Bazaviy valyuta uchun kurs kerak emas."))
        if self.rate is not None and self.rate <= 0:
            raise ValidationError(_("Kurs musbat bo‘lishi kerak."))
