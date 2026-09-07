from decimal import Decimal

from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.db import models

from core.models import TenantOwnedModel


class Company(TenantOwnedModel):
    name = models.CharField(_("Nomi"), max_length=200)
    inn = models.CharField(_("INN"), max_length=32, blank=True)
    phone = models.CharField(_("Telefon"), max_length=32, blank=True)
    email = models.EmailField(_("Email"), blank=True)
    address = models.CharField(_("Manzil"), max_length=500, blank=True)
    notes = models.TextField(_("Izoh"), blank=True)
    is_active = models.BooleanField(_("Faol"), default=True)
    payment_terms_days = models.PositiveIntegerField(
        _("To‘lov muddati (kun)"),
        default=30,
        blank=True,
        help_text=_("Bo‘sh qoldirilsa 30 kun."),
    )
    credit_limit = models.DecimalField(
        _("Kredit limiti"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0"),
        blank=True,
        help_text=_("Bo‘sh qoldirilsa 0."),
    )

    class Meta:
        verbose_name = _("Kompaniya")
        verbose_name_plural = _("Kompaniyalar")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "name"),
                name="guests_company_tenant_name_uniq",
                violation_error_message=_(
                    "Bu mehmonxonada shu nomli kompaniya allaqachon mavjud. "
                    "Boshqa nom tanlang yoki mavjud kompaniyani tahrirlang."
                ),
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self):
        super().clean()
        if self.payment_terms_days is None:
            self.payment_terms_days = 30
        if self.credit_limit is None:
            self.credit_limit = Decimal("0")

    def save(self, *args, **kwargs):
        if self.payment_terms_days is None:
            self.payment_terms_days = 30
        if self.credit_limit is None:
            self.credit_limit = Decimal("0")
        super().save(*args, **kwargs)


class Guest(TenantOwnedModel):
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    nationality = models.CharField(max_length=80, blank=True)
    is_vip = models.BooleanField(default=False)
    is_blacklisted = models.BooleanField(default=False)
    blacklist_reason = models.CharField(max_length=255, blank=True)
    company = models.ForeignKey(
        Company, on_delete=models.SET_NULL, null=True, blank=True, related_name="guests"
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self) -> str:
        return self.full_name

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class GuestDocument(TenantOwnedModel):
    class DocType(models.TextChoices):
        PASSPORT = "passport", _("Pasport")
        ID_CARD = "id_card", _("ID karta")
        OTHER = "other", _("Boshqa")

    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name="documents")
    doc_type = models.CharField(max_length=20, choices=DocType.choices, default=DocType.PASSPORT)
    number = models.CharField(max_length=64)
    issued_country = models.CharField(max_length=80, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    file = models.FileField(upload_to="guest_docs/%Y/%m/", blank=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self) -> str:
        return f"{self.get_doc_type_display()} {self.number}"


class GuestNote(TenantOwnedModel):
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name="guest_notes")
    body = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="guest_notes_created",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.body[:40]
