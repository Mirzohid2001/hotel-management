from decimal import Decimal

from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.currency import CURRENCY_CHOICES, MoneyFieldsMixin, apply_money
from core.models import TenantOwnedModel


class ReservationGroup(TenantOwnedModel):
    """Corporate / multi-room group booking shell."""

    code = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=200)
    hotel = models.ForeignKey(
        "properties.Property", on_delete=models.PROTECT, related_name="reservation_groups"
    )
    company = models.ForeignKey(
        "guests.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservation_groups",
    )
    check_in = models.DateField()
    check_out = models.DateField()
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservation_groups_created",
    )

    class Meta:
        ordering = ["-check_in", "-id"]
        unique_together = ("tenant", "code")

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"


class ReservationQuerySet(models.QuerySet):
    def overlapping(self, check_in, check_out, *, room=None, exclude_pk=None):
        """Reservations that overlap [check_in, check_out) for an optional room."""
        active = self.exclude(
            status__in=[
                Reservation.Status.CANCELLED,
                Reservation.Status.NO_SHOW,
                Reservation.Status.CHECKED_OUT,
            ]
        )
        qs = active.filter(check_in__lt=check_out, check_out__gt=check_in)
        if room is not None:
            qs = qs.filter(room=room)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        return qs


class BookingReferrer(TenantOwnedModel):
    """External agent / person who sends guests and earns a commission %."""

    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=32, blank=True)
    default_commission_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0"),
        help_text=_("Bron yaratilganda foiz shu qiymatdan to‘ldiriladi."),
    )
    notes = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")
        verbose_name = _("Yo‘naltiruvchi")
        verbose_name_plural = _("Yo‘naltiruvchilar")

    def __str__(self) -> str:
        return self.name


class ReferrerCommissionPayment(MoneyFieldsMixin, TenantOwnedModel):
    """Yo‘naltiruvchiga berilgan komissiya to‘lovi (oylik davr uchun)."""

    class Method(models.TextChoices):
        CASH = "cash", _("Naqd")
        CARD = "card", _("Karta")
        TRANSFER = "transfer", _("O‘tkazma")

    referrer = models.ForeignKey(
        BookingReferrer,
        on_delete=models.CASCADE,
        related_name="commission_payments",
    )
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    paid_on = models.DateField()
    method = models.CharField(
        max_length=20, choices=Method.choices, default=Method.CASH
    )
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referrer_commission_payments",
    )

    class Meta:
        ordering = ["-paid_on", "-id"]

    def save(self, *args, **kwargs):
        apply_money(self, on_date=self.paid_on)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.referrer} · {self.year}-{self.month:02d} · {self.amount} {self.currency}"


class Reservation(TenantOwnedModel):
    class Status(models.TextChoices):
        INQUIRY = "inquiry", _("So‘rov")
        CONFIRMED = "confirmed", _("Tasdiqlangan")
        CHECKED_IN = "checked_in", _("Joylashgan")
        CHECKED_OUT = "checked_out", _("Chiqgan")
        CANCELLED = "cancelled", _("Bekor qilingan")
        NO_SHOW = "no_show", _("Kelmagan")

    class Source(models.TextChoices):
        WALKIN = "walkin", _("Darhol")
        PHONE = "phone", _("Telefon")
        WEBSITE = "website", _("Veb-sayt")
        OTHER = "other", _("Boshqa")

    code = models.CharField(max_length=32, db_index=True)
    hotel = models.ForeignKey(
        "properties.Property", on_delete=models.PROTECT, related_name="reservations"
    )
    guest = models.ForeignKey(
        "guests.Guest", on_delete=models.PROTECT, related_name="reservations"
    )
    company = models.ForeignKey(
        "guests.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations",
    )
    group = models.ForeignKey(
        ReservationGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations",
    )
    referrer = models.ForeignKey(
        BookingReferrer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations",
    )
    commission_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Yo‘naltiruvchiga bron summasidan foiz."),
    )
    room_type = models.ForeignKey(
        "properties.RoomType", on_delete=models.PROTECT, related_name="reservations"
    )
    room = models.ForeignKey(
        "properties.Room",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations",
    )
    rate_plan = models.ForeignKey(
        "properties.RatePlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations",
    )
    nightly_rate = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Qo‘lda kelishilgan 1 kecha narxi (tarif o‘rniga).",
    )
    emehmon_required = models.BooleanField(
        default=True,
        help_text=_("True — E-mehmon: tarif × kecha × mehmon; False — bu bronda olinmaydi."),
    )
    check_in = models.DateField()
    check_out = models.DateField()
    adults = models.PositiveSmallIntegerField(default=1)
    children = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CONFIRMED)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.PHONE)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="UZS")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations_created",
    )

    objects = ReservationQuerySet.as_manager()

    class Meta:
        ordering = ["-check_in", "-id"]
        unique_together = ("tenant", "code")

    def __str__(self) -> str:
        return self.code

    def clean(self):
        if self.check_in and self.check_out and self.check_out <= self.check_in:
            raise ValidationError({"check_out": "Check-out must be after check-in."})
        if self.room_id and self.room and self.room.status == self.room.Status.OUT_OF_ORDER:
            if self.status in {self.Status.CONFIRMED, self.Status.CHECKED_IN}:
                raise ValidationError({"room": "Room is out of order."})

    @property
    def nights(self) -> int:
        if not self.check_in or not self.check_out:
            return 0
        return (self.check_out - self.check_in).days


class Stay(TenantOwnedModel):
    reservation = models.OneToOneField(
        Reservation, on_delete=models.CASCADE, related_name="stay"
    )
    actual_check_in = models.DateTimeField()
    actual_check_out = models.DateTimeField(null=True, blank=True)
    checked_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stays_checked_in",
    )
    checked_out_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stays_checked_out",
    )

    def __str__(self) -> str:
        return f"Stay {self.reservation.code}"


class ReservationChangeLog(TenantOwnedModel):
    reservation = models.ForeignKey(
        Reservation, on_delete=models.CASCADE, related_name="change_logs"
    )
    field = models.CharField(max_length=64)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    reason = models.CharField(max_length=255, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservation_changes",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.reservation.code}: {self.field}"
