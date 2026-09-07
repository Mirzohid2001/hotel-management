from datetime import date
from decimal import Decimal

from django.utils.translation import gettext_lazy as _
from django.db import models
from django.utils import timezone


DEFAULT_PLAN_LIMITS = {
    "free": {
        "rooms": 10,
        "users": 2,
        "properties": 1,
        "features": ["folio_cash", "basic_dashboard"],
    },
    "basic": {
        "rooms": 50,
        "users": 10,
        "properties": 3,
        "features": [
            "folio_cash",
            "folio_card",
            "basic_dashboard",
            "housekeeping",
            "booking_amend",
            "services",
            "expenses",
            "maintenance",
            "multi_rate",
            "reports_basic",
            "online_booking",
        ],
    },
    "pro": {
        "rooms": None,
        "users": None,
        "properties": None,
        "features": [
            "folio_cash",
            "folio_card",
            "folio_transfer",
            "basic_dashboard",
            "housekeeping",
            "booking_amend",
            "services",
            "expenses",
            "maintenance",
            "multi_rate",
            "season_rates",
            "reports_basic",
            "reports_advanced",
            "csv_export",
            "payroll",
            "inventory",
            "cash_shift",
            "night_audit",
            "company_group",
            "pnl",
            "online_booking",
        ],
    },
}


class Plan(models.Model):
    class Code(models.TextChoices):
        FREE = "free", _("Bepul")
        BASIC = "basic", _("Asosiy")
        PRO = "pro", _("Pro")

    code = models.CharField(max_length=32, choices=Code.choices, unique=True)
    name = models.CharField(max_length=100)
    price_monthly = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    price_yearly = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    limits = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["price_monthly"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.limits:
            self.limits = DEFAULT_PLAN_LIMITS.get(self.code, {}).copy()
        super().save(*args, **kwargs)


class Subscription(models.Model):
    class Status(models.TextChoices):
        TRIAL = "trial", _("Sinov")
        ACTIVE = "active", _("Faol")
        EXPIRED = "expired", _("Muddati tugagan")
        CANCELLED = "cancelled", _("Bekor qilingan")

    class BillingPeriod(models.TextChoices):
        MONTHLY = "monthly", _("Har oy")
        YEARLY = "yearly", _("Har yil")

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    billing_period = models.CharField(
        max_length=16, choices=BillingPeriod.choices, default=BillingPeriod.MONTHLY
    )
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_end"]

    def __str__(self) -> str:
        return f"{self.tenant} — {self.plan} ({self.status})"

    def is_currently_valid(self, on_date: date | None = None) -> bool:
        day = on_date or timezone.localdate()
        if self.status not in {self.Status.ACTIVE, self.Status.TRIAL}:
            return False
        return self.period_start <= day <= self.period_end

    def sync_status_with_dates(self):
        day = timezone.localdate()
        if self.status == self.Status.CANCELLED:
            return
        if day > self.period_end:
            self.status = self.Status.EXPIRED
        elif self.status == self.Status.EXPIRED and self.period_start <= day <= self.period_end:
            self.status = self.Status.ACTIVE
