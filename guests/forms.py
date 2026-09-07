from decimal import Decimal

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Company, Guest, GuestDocument, GuestNote


class GuestForm(forms.ModelForm):
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
        if tenant is not None:
            self.fields["company"].queryset = Company.objects.filter(tenant=tenant, is_active=True)


class GuestQuickForm(forms.Form):
    first_name = forms.CharField(max_length=120, label=_("Ism"))
    last_name = forms.CharField(required=False, max_length=120, label=_("Familiya"))
    phone = forms.CharField(required=False, max_length=32, label=_("Telefon"))


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
