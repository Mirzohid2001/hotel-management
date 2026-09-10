from decimal import Decimal

from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.db import models

from core.currency import CURRENCY_CHOICES, MoneyFieldsMixin, apply_money
from core.models import TenantOwnedModel


class ExpenseCategory(TenantOwnedModel):
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "expense categories"
        unique_together = ("tenant", "name")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Vendor(TenantOwnedModel):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=32, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")

    def __str__(self) -> str:
        return self.name


class Expense(MoneyFieldsMixin, TenantOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", _("Qoralama")
        APPROVED = "approved", _("Tasdiqlangan")
        PAID = "paid", _("To‘langan")
        REJECTED = "rejected", _("Rad etilgan")

    class PaymentMethod(models.TextChoices):
        CASH = "cash", _("Naqd")
        CARD = "card", _("Karta")
        TRANSFER = "transfer", _("O‘tkazma")

    class Funding(models.TextChoices):
        """Joriy → Sof (P&L); reinvestitsiya → faqat uchreditel foyda ulushi."""

        OPERATING = "operating", _("Joriy (Sofdan)")
        REINVESTMENT = "reinvestment", _("Reinvestitsiya (foydadan)")

    hotel = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="expenses",
        null=True,
        blank=True,
    )
    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.PROTECT, related_name="expenses"
    )
    vendor = models.ForeignKey(
        Vendor, on_delete=models.SET_NULL, null=True, blank=True, related_name="expenses"
    )
    maintenance_ticket = models.ForeignKey(
        "maintenance.MaintenanceTicket",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
        verbose_name=_("Ta’mir arizasi"),
    )
    funding = models.CharField(
        max_length=20,
        choices=Funding.choices,
        default=Funding.OPERATING,
        verbose_name=_("Moliyalashtirish"),
        help_text=_(
            "Joriy — mehmonxona Sofidan. Reinvestitsiya — Sofga tegmaydi, "
            "uchreditel/foyda ulushidan ayiriladi."
        ),
    )
    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    expense_date = models.DateField()
    payment_method = models.CharField(
        max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    receipt = models.FileField(upload_to="expenses/%Y/%m/", blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses_created",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses_approved",
    )
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses_rejected",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses_paid",
    )
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-expense_date", "-id"]

    def save(self, *args, **kwargs):
        apply_money(self, on_date=self.expense_date)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.title} ({self.amount} {self.currency})"


class ProfitPartner(TenantOwnedModel):
    """Equity partner who shares hotel net profit by percent."""

    name = models.CharField(max_length=200, verbose_name=_("Ism"))
    share_percent = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        verbose_name=_("Ulush %"),
        help_text=_("Masalan 30.00 — sof foydaning 30 foizi."),
    )
    phone = models.CharField(max_length=32, blank=True, verbose_name=_("Telefon"))
    notes = models.TextField(blank=True, verbose_name=_("Izoh"))
    is_active = models.BooleanField(default=True, verbose_name=_("Faol"))

    class Meta:
        ordering = ["-share_percent", "name"]
        unique_together = ("tenant", "name")
        verbose_name = _("Foyda sherigi")
        verbose_name_plural = _("Foyda sheriklari")

    def __str__(self) -> str:
        return f"{self.name} ({self.share_percent}%)"


class ProfitPeriod(TenantOwnedModel):
    """
    Accounting window for partner profit shares.
    Closing a period zeros the running ledger and starts a fresh window.
    """

    started_on = models.DateField(verbose_name=_("Boshlanish"))
    ended_on = models.DateField(null=True, blank=True, verbose_name=_("Tugash"))
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profit_periods_closed",
    )
    note = models.CharField(max_length=255, blank=True, verbose_name=_("Izoh"))
    # Snapshot at close for history (optional)
    net_snapshot = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )

    class Meta:
        ordering = ["-started_on", "-id"]
        verbose_name = _("Foyda davri")
        verbose_name_plural = _("Foyda davrlari")

    def __str__(self) -> str:
        end = self.ended_on.isoformat() if self.ended_on else "…"
        return f"{self.started_on} → {end}"

    @property
    def is_open(self) -> bool:
        return self.ended_on is None


class ProfitWithdrawal(MoneyFieldsMixin, TenantOwnedModel):
    """Partner took (part of) their share from the open/current period."""

    class PaymentMethod(models.TextChoices):
        CASH = "cash", _("Naqd")
        CARD = "card", _("Karta")
        TRANSFER = "transfer", _("O‘tkazma")

    period = models.ForeignKey(
        ProfitPeriod, on_delete=models.CASCADE, related_name="withdrawals"
    )
    partner = models.ForeignKey(
        ProfitPartner, on_delete=models.PROTECT, related_name="withdrawals"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2, verbose_name=_("Summa"))
    paid_on = models.DateField(verbose_name=_("Sana"))
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
        verbose_name=_("Usul"),
    )
    note = models.CharField(max_length=255, blank=True, verbose_name=_("Izoh"))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profit_withdrawals_created",
    )

    class Meta:
        ordering = ["-paid_on", "-id"]
        verbose_name = _("Foyda olish")
        verbose_name_plural = _("Foyda olishlar")

    def save(self, *args, **kwargs):
        apply_money(self, on_date=self.paid_on)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.partner_id}: {self.amount} {self.currency}"
