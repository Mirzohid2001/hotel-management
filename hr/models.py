from decimal import Decimal

from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.db import models
from django.db.models import Q

from core.currency import CURRENCY_CHOICES, MoneyFieldsMixin, apply_money
from core.models import TenantOwnedModel


class Employee(TenantOwnedModel):
    class SalaryType(models.TextChoices):
        MONTHLY = "monthly", _("Oylik maosh")
        DAILY = "daily", _("Kunlik")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_profiles",
    )
    full_name = models.CharField(max_length=200)
    position = models.CharField(max_length=120, blank=True)
    salary_type = models.CharField(
        max_length=20, choices=SalaryType.choices, default=SalaryType.MONTHLY
    )
    base_salary = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0"),
        help_text=_("Oylik: oyiga. Kunlik: bir kunlik stavka."),
    )
    hire_date = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self) -> str:
        return self.full_name

    @property
    def is_daily(self) -> bool:
        return self.salary_type == self.SalaryType.DAILY


class PayrollPeriod(TenantOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", _("Qoralama")
        FINALIZED = "finalized", _("Yakunlangan")
        PAID = "paid", _("To‘langan")

    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    class Meta:
        unique_together = ("tenant", "year", "month")
        ordering = ["-year", "-month"]

    def __str__(self) -> str:
        return f"{self.year}-{self.month:02d}"


class PayrollItem(TenantOwnedModel):
    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name="items")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="payroll_items")
    work_date = models.DateField(
        null=True,
        blank=True,
        help_text=_("Kunlik ish kuni. Oylik qatorda bo‘sh qoladi."),
    )
    days_count = models.PositiveSmallIntegerField(
        default=1,
        help_text=_("Kunlik to‘lovda necha kun. Oylikda 1."),
    )
    base_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    bonus = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    deduction = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    advance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    net_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["period", "employee"],
                condition=Q(work_date__isnull=True),
                name="hr_payrollitem_monthly_unique",
            ),
            models.UniqueConstraint(
                fields=["period", "employee", "work_date"],
                condition=Q(work_date__isnull=False),
                name="hr_payrollitem_daily_unique",
            ),
        ]

    @property
    def gross_amount(self) -> Decimal:
        raw = (
            (self.base_amount or Decimal("0"))
            + (self.bonus or Decimal("0"))
            - (self.deduction or Decimal("0"))
        )
        return raw if raw > 0 else Decimal("0")

    def recompute(self):
        raw = self.gross_amount - (self.advance or Decimal("0"))
        self.net_amount = raw if raw > 0 else Decimal("0")

    def save(self, *args, **kwargs):
        self.recompute()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        if self.work_date:
            return f"{self.employee} · {self.work_date}"
        return f"{self.employee} · {self.period}"

class SalaryAdvance(MoneyFieldsMixin, TenantOwnedModel):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="advances")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    advance_date = models.DateField()
    note = models.CharField(max_length=255, blank=True)
    is_settled = models.BooleanField(default=False)
    recovered_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0"),
        help_text=_("Oylikdan ushlangan qism (qisman qoplash)."),
    )
    applied_to_period = models.ForeignKey(
        PayrollPeriod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applied_advances",
    )

    class Meta:
        ordering = ["-advance_date"]

    def save(self, *args, **kwargs):
        apply_money(self, on_date=self.advance_date)
        super().save(*args, **kwargs)

    @property
    def principal(self) -> Decimal:
        return self.amount_base if self.amount_base is not None else self.amount

    @property
    def open_amount(self) -> Decimal:
        """Hali oylikdan ushlanmagan qoldiq."""
        left = self.principal - (self.recovered_amount or Decimal("0"))
        return left if left > 0 else Decimal("0")

    def __str__(self) -> str:
        return f"{self.employee} · {self.amount} {self.currency}"


class SalaryPayment(MoneyFieldsMixin, TenantOwnedModel):
    item = models.OneToOneField(PayrollItem, on_delete=models.CASCADE, related_name="payment")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    paid_at = models.DateTimeField()
    method = models.CharField(max_length=20, default="cash")
    note = models.CharField(max_length=255, blank=True)

    def save(self, *args, **kwargs):
        on_date = self.paid_at.date() if self.paid_at else None
        apply_money(self, on_date=on_date)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"
