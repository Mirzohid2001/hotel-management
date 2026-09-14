from decimal import Decimal

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Company, Guest, GuestDocument, GuestNote


def primary_id_document(guest):
    """Latest passport or ID card for a guest profile."""
    if guest is None or not guest.pk:
        return None
    return (
        guest.documents.filter(
            doc_type__in=[GuestDocument.DocType.PASSPORT, GuestDocument.DocType.ID_CARD]
        )
        .order_by("-id")
        .first()
    )


class GuestForm(forms.ModelForm):
    doc_type = forms.ChoiceField(
        required=False,
        label=_("Hujjat turi"),
        choices=[
            (GuestDocument.DocType.PASSPORT, _("Pasport")),
            (GuestDocument.DocType.ID_CARD, _("ID karta")),
        ],
        initial=GuestDocument.DocType.PASSPORT,
    )
    doc_number = forms.CharField(
        required=False,
        max_length=64,
        label=_("Pasport / ID raqami"),
        widget=forms.TextInput(attrs={"placeholder": "AA 1234567", "autocomplete": "off"}),
    )
    issued_country = forms.CharField(
        required=False,
        max_length=80,
        label=_("Berilgan mamlakat"),
        widget=forms.TextInput(attrs={"placeholder": "UZ"}),
    )

    class Meta:
        model = Guest
        fields = (
            "first_name",
            "last_name",
            "phone",
            "email",
            "nationality",
            "company",
            "is_vip",
            "is_blacklisted",
            "blacklist_reason",
            "notes",
        )
        labels = {
            "first_name": _("Ism"),
            "last_name": _("Familiya"),
            "phone": _("Telefon"),
            "email": _("Email"),
            "nationality": _("Fuqarolik"),
            "company": _("Kompaniya"),
            "is_vip": _("VIP"),
            "is_blacklisted": _("Qora ro‘yxat"),
            "blacklist_reason": _("Qora ro‘yxat sababi"),
            "notes": _("Izoh"),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        if tenant is not None:
            self.fields["company"].queryset = Company.objects.filter(tenant=tenant, is_active=True)
        # Fuqarolikdan keyin pasport — tahrirda ham ko‘rinsin.
        ordered = [
            "first_name",
            "last_name",
            "phone",
            "email",
            "nationality",
            "doc_type",
            "doc_number",
            "issued_country",
            "company",
            "is_vip",
            "is_blacklisted",
            "blacklist_reason",
            "notes",
        ]
        self.order_fields(ordered)

        doc = primary_id_document(self.instance) if self.instance and self.instance.pk else None
        if doc is not None and not self.is_bound:
            self.fields["doc_type"].initial = doc.doc_type
            self.fields["doc_number"].initial = doc.number
            self.fields["issued_country"].initial = doc.issued_country or "UZ"
        elif not self.is_bound:
            self.fields["issued_country"].initial = "UZ"

    def clean_doc_number(self):
        return (self.cleaned_data.get("doc_number") or "").strip()

    def save(self, commit=True):
        guest = super().save(commit=commit)
        if commit:
            self.save_identity_document(guest)
        return guest

    def save_identity_document(self, guest):
        number = (self.cleaned_data.get("doc_number") or "").strip()
        if not number:
            return None
        doc_type = (
            self.cleaned_data.get("doc_type") or GuestDocument.DocType.PASSPORT
        )
        issued = (self.cleaned_data.get("issued_country") or "").strip()
        tenant = self.tenant or guest.tenant
        doc = primary_id_document(guest)
        if doc is None:
            return GuestDocument.objects.create(
                tenant=tenant,
                guest=guest,
                doc_type=doc_type,
                number=number,
                issued_country=issued,
            )
        doc.doc_type = doc_type
        doc.number = number
        doc.issued_country = issued
        doc.save(update_fields=["doc_type", "number", "issued_country", "updated_at"])
        return doc


class GuestQuickForm(forms.Form):
    """Bron/walk-in dan tezkor mehmon — check-in uchun pasport majburiy."""

    first_name = forms.CharField(max_length=120, label=_("Ism"))
    last_name = forms.CharField(required=False, max_length=120, label=_("Familiya"))
    phone = forms.CharField(required=False, max_length=32, label=_("Telefon"))
    nationality = forms.CharField(
        required=False,
        max_length=80,
        label=_("Fuqarolik"),
        initial="UZ",
        widget=forms.TextInput(attrs={"placeholder": "UZ"}),
    )
    doc_type = forms.ChoiceField(
        label=_("Hujjat turi"),
        choices=[
            (GuestDocument.DocType.PASSPORT, _("Pasport")),
            (GuestDocument.DocType.ID_CARD, _("ID karta")),
        ],
        initial=GuestDocument.DocType.PASSPORT,
    )
    doc_number = forms.CharField(
        max_length=64,
        label=_("Pasport / ID raqami"),
        widget=forms.TextInput(attrs={"placeholder": "AA 1234567", "autocomplete": "off"}),
    )
    issued_country = forms.CharField(
        required=False,
        max_length=80,
        label=_("Berilgan mamlakat"),
        initial="UZ",
        widget=forms.TextInput(attrs={"placeholder": "UZ"}),
    )

    def clean_doc_number(self):
        number = (self.cleaned_data.get("doc_number") or "").strip()
        if not number:
            raise forms.ValidationError(_("Kirish (zayezd) uchun hujjat raqami kerak."))
        return number


class GuestDocumentForm(forms.ModelForm):
    class Meta:
        model = GuestDocument
        fields = ("doc_type", "number", "issued_country", "expiry_date", "file")
        labels = {
            "doc_type": _("Hujjat turi"),
            "number": _("Raqam"),
            "issued_country": _("Berilgan mamlakat"),
            "expiry_date": _("Amal qilish muddati"),
            "file": _("Fayl"),
        }


class GuestNoteForm(forms.ModelForm):
    class Meta:
        model = GuestNote
        fields = ("body",)
        labels = {"body": _("Izoh")}


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = (
            "name",
            "inn",
            "phone",
            "email",
            "address",
            "notes",
            "is_active",
            "payment_terms_days",
            "credit_limit",
        )
        labels = {
            "name": _("Nomi"),
            "inn": _("INN"),
            "phone": _("Telefon"),
            "email": _("Email"),
            "address": _("Manzil"),
            "notes": _("Izoh"),
            "is_active": _("Faol"),
            "payment_terms_days": _("To‘lov muddati (kun)"),
            "credit_limit": _("Kredit limiti"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Admin/forma bo‘sh qoldirilsa default qo‘llanadi (required xato bermasligi uchun).
        if "payment_terms_days" in self.fields:
            self.fields["payment_terms_days"].required = False
        if "credit_limit" in self.fields:
            self.fields["credit_limit"].required = False

    def clean_payment_terms_days(self):
        value = self.cleaned_data.get("payment_terms_days")
        return 30 if value is None else value

    def clean_credit_limit(self):
        value = self.cleaned_data.get("credit_limit")
        return Decimal("0") if value is None else value


class CompanyAdminForm(CompanyForm):
    """Admin: tenant majburiy; bo‘sh raqam maydonlari defaultga tushadi."""

    class Meta(CompanyForm.Meta):
        fields = (
            "tenant",
            "name",
            "inn",
            "phone",
            "email",
            "address",
            "notes",
            "is_active",
            "payment_terms_days",
            "credit_limit",
        )
        labels = {
            **CompanyForm.Meta.labels,
            "tenant": _("Mehmonxona (tenant)"),
        }
        help_texts = {
            "tenant": _("Kompaniya qaysi mehmonxonaga tegishli — majburiy."),
            "name": _("Shu mehmonxonada takrorlanmasligi kerak."),
        }


class CompanyQuickForm(forms.Form):
    name = forms.CharField(max_length=200, label=_("Nomi"))
    phone = forms.CharField(required=False, max_length=32, label=_("Telefon"))
    inn = forms.CharField(required=False, max_length=32, label=_("INN"))
