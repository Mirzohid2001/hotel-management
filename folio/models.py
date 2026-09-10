from decimal import Decimal

from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from core.currency import MoneyFieldsMixin, apply_money, money_sum
from core.models import TenantOwnedModel


class Folio(TenantOwnedModel):
    stay = models.OneToOneField(
        "bookings.Stay",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="folio",
    )
    reservation = models.OneToOneField(
        "bookings.Reservation", on_delete=models.CASCADE, related_name="folio"
    )
    is_open = models.BooleanField(default=True)
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opened_at"]

    def __str__(self) -> str:
        return f"Folio {self.reservation.code}"

    @property
    def base_currency(self) -> str:
        return getattr(self.tenant, "currency", None) or "UZS"

    @property
    def charges_total(self) -> Decimal:
        """Bazaviy valyutadagi xarajatlar jami (hisobot/balans)."""
        return money_sum(self.charges.filter(is_void=False))

    @property
    def payments_total(self) -> Decimal:
        """Net to‘lovlar: kirim − sdachi/qaytarish (bazaviy valyuta)."""
        incoming = money_sum(
            self.payments.filter(is_void=False).exclude(kind=GuestPayment.Kind.REFUND)
        )
        refunds = money_sum(
            self.payments.filter(is_void=False, kind=GuestPayment.Kind.REFUND)
        )
        return incoming - refunds

    @property
    def tax_percent(self) -> Decimal:
        from properties.models import PropertySettings

        settings = PropertySettings.objects.filter(property_id=self.reservation.hotel_id).first()
        if not settings:
            return Decimal("0")
        return settings.tax_percent or Decimal("0")

    @property
    def tax_amount(self) -> Decimal:
        if self.tax_percent <= 0:
            return Decimal("0")
        return (self.charges_total * self.tax_percent / Decimal("100")).quantize(Decimal("0.01"))

    @property
    def grand_total(self) -> Decimal:
        """Charges + VAT (bazaviy valyuta)."""
        return self.charges_total + self.tax_amount

    @property
    def balance(self) -> Decimal:
        return self.grand_total - self.payments_total

    @property
    def amount_due(self) -> Decimal:
        """Only the unpaid due part; never negative."""
        return self.balance if self.balance > 0 else Decimal("0")

    @property
    def credit_amount(self) -> Decimal:
        """Guest overpayment / advance currently sitting on the folio."""
        return -self.balance if self.balance < 0 else Decimal("0")


class FolioCharge(MoneyFieldsMixin, TenantOwnedModel):
    class ChargeType(models.TextChoices):
        ROOM = "room", _("Yashash")
        SERVICE = "service", _("Xizmat")
        MINIBAR = "minibar", _("Minibar")
        PENALTY = "penalty", _("Jarima")
        CANCEL = "cancel", _("Bekor qilish to‘lovi")
        EMEHMON = "emehmon", _("E-mehmon")
        OTHER = "other", _("Boshqa")

    folio = models.ForeignKey(Folio, on_delete=models.CASCADE, related_name="charges")
    charge_type = models.CharField(max_length=20, choices=ChargeType.choices, default=ChargeType.OTHER)
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1"))
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    is_void = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=255, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="voided_folio_charges",
    )
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="folio_charges",
    )

    class Meta:
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        self.amount = (self.quantity or Decimal("0")) * (self.unit_price or Decimal("0"))
        apply_money(self, tenant=getattr(self, "tenant", None) or getattr(self.folio, "tenant", None))
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.description}: {self.amount} {self.currency}"


class GuestPayment(MoneyFieldsMixin, TenantOwnedModel):
    class Method(models.TextChoices):
        CASH = "cash", _("Naqd")
        CARD = "card", _("Karta")
        TRANSFER = "transfer", _("O‘tkazma")

    class Kind(models.TextChoices):
        PAYMENT = "payment", _("To‘lov")
        DEPOSIT = "deposit", _("Depozit")
        REFUND = "refund", _("Sdachi / qaytarish")
        CITY_LEDGER = "city_ledger", _("Kompaniya hisobi")

    folio = models.ForeignKey(Folio, on_delete=models.CASCADE, related_name="payments")
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.CASH)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.PAYMENT)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)
    is_void = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=255, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="voided_guest_payments",
    )
    cash_shift = models.ForeignKey(
        "CashShift",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="guest_payments",
    )

    class Meta:
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        apply_money(self, tenant=getattr(self, "tenant", None) or getattr(self.folio, "tenant", None))
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.method} {self.amount} {self.currency}"

    @property
    def is_refund(self) -> bool:
        return self.kind == self.Kind.REFUND

    @property
    def signed_amount_base(self) -> Decimal:
        base = self.amount_base if self.amount_base is not None else self.amount
        return -base if self.is_refund else base


class CashShift(TenantOwnedModel):
    hotel = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="cash_shifts",
        null=True,
        blank=True,
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cash_shifts_opened",
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cash_shifts_closed",
    )
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    opening_float = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    closing_cash = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    variance = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-opened_at"]

    def __str__(self) -> str:
        return f"Shift {self.opened_at:%Y-%m-%d %H:%M}"

    @property
    def is_open(self) -> bool:
        return self.closed_at is None


class CashShiftMovement(MoneyFieldsMixin, TenantOwnedModel):
    """Manual drawer pay-in / pay-out during an open cash shift."""

    class Kind(models.TextChoices):
        PAY_IN = "pay_in", _("Kassa kirim")
        PAY_OUT = "pay_out", _("Kassa chiqim")

    shift = models.ForeignKey(
        CashShift, on_delete=models.CASCADE, related_name="movements"
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cash_shift_movements",
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = _("Kassa harakati")
        verbose_name_plural = _("Kassa harakatlari")

    def save(self, *args, **kwargs):
        apply_money(self, tenant=getattr(self, "tenant", None) or getattr(self.shift, "tenant", None))
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.kind} {self.amount} {self.currency}"


class CompanyInvoice(TenantOwnedModel):
    class Status(models.TextChoices):
        OPEN = "open", _("Ochiq")
        PARTIAL = "partial", _("Qisman")
        PAID = "paid", _("To‘langan")
        VOID = "void", _("Bekor")

    company = models.ForeignKey(
        "guests.Company", on_delete=models.PROTECT, related_name="invoices"
    )
    hotel = models.ForeignKey(
        "properties.Property",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="company_invoices",
    )
    code = models.CharField(max_length=32)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    issued_at = models.DateTimeField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    source_folio = models.ForeignKey(
        Folio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="company_invoices",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="company_invoices_created",
    )

    class Meta:
        ordering = ["-issued_at", "-id"]
        unique_together = ("tenant", "code")

    def __str__(self) -> str:
        return self.code

    @property
    def lines_total(self) -> Decimal:
        return money_sum(self.lines.all())

    @property
    def payments_total(self) -> Decimal:
        return money_sum(self.payments.filter(is_void=False))

    @property
    def balance(self) -> Decimal:
        if self.status == self.Status.VOID:
            return Decimal("0")
        return self.lines_total - self.payments_total

    def refresh_status(self):
        if self.status == self.Status.VOID:
            return
        bal = self.balance
        if bal <= 0 and self.lines_total > 0:
            self.status = self.Status.PAID
        elif self.payments_total > 0:
            self.status = self.Status.PARTIAL
        else:
            self.status = self.Status.OPEN
        self.save(update_fields=["status", "updated_at"])


class CompanyInvoiceLine(MoneyFieldsMixin, TenantOwnedModel):
    invoice = models.ForeignKey(
        CompanyInvoice, on_delete=models.CASCADE, related_name="lines"
    )
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    source_charge = models.ForeignKey(
        FolioCharge,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="city_ledger_lines",
    )
    source_reservation = models.ForeignKey(
        "bookings.Reservation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="city_ledger_lines",
    )

    class Meta:
        ordering = ["id"]

    def save(self, *args, **kwargs):
        apply_money(
            self, tenant=getattr(self, "tenant", None) or getattr(self.invoice, "tenant", None)
        )
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.description}: {self.amount} {self.currency}"


class CompanyPayment(MoneyFieldsMixin, TenantOwnedModel):
    invoice = models.ForeignKey(
        CompanyInvoice, on_delete=models.CASCADE, related_name="payments"
    )
    method = models.CharField(
        max_length=20, choices=GuestPayment.Method.choices, default=GuestPayment.Method.TRANSFER
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)
    is_void = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=255, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="voided_company_payments",
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="company_payments",
    )

    class Meta:
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        apply_money(
            self, tenant=getattr(self, "tenant", None) or getattr(self.invoice, "tenant", None)
        )
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.method} {self.amount} {self.currency}"
