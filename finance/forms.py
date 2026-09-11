from django import forms
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from core.currency import CURRENCY_CHOICES
from tenants.models import ExchangeRate, Tenant

from .models import Expense, ExpenseCategory, ProfitPartner, ProfitWithdrawal, Vendor


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = (
            "category",
            "vendor",
            "title",
            "amount",
            "currency",
            "expense_date",
            "payment_method",
            "funding",
            "receipt",
            "notes",
        )
        labels = {
            "category": _("Kategoriya"),
            "vendor": _("Yetkazib beruvchi"),
            "title": _("Sarlavha"),
            "amount": _("Summa"),
            "currency": _("Valyuta"),
            "expense_date": _("Sana"),
            "payment_method": _("To‘lov usuli"),
            "funding": _("Moliyalashtirish"),
            "receipt": _("Chek"),
            "notes": _("Izoh"),
        }
        help_texts = {
            "funding": _(
                "Joriy — sof foydadan. Reinvestitsiya — sof foydaga tegmaydi, ulushi katta sherikdan."
            ),
        }
        widgets = {"expense_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["currency"].initial = tenant.currency or "UZS"
            cats = ExpenseCategory.objects.filter(tenant=tenant, is_active=True)
            vendors = Vendor.objects.filter(tenant=tenant, is_active=True)
            # Tahrirlashda hozirgi (faol emas) qiymatlar ham tanlovda qolsin
            if self.instance and self.instance.pk:
                if self.instance.category_id:
                    cats = ExpenseCategory.objects.filter(
                        Q(pk=self.instance.category_id) | Q(tenant=tenant, is_active=True)
                    ).distinct()
                if self.instance.vendor_id:
                    vendors = Vendor.objects.filter(
                        Q(pk=self.instance.vendor_id) | Q(tenant=tenant, is_active=True)
                    ).distinct()
            self.fields["category"].queryset = cats.order_by("name")
            self.fields["vendor"].queryset = vendors.order_by("name")
            self.fields["vendor"].required = False

    def clean(self):
        cleaned = super().clean()
        category = cleaned.get("category")
        funding = cleaned.get("funding")
        if category and funding:
            name = (category.name or "").strip().lower()
            if "reinvest" in name and funding != Expense.Funding.REINVESTMENT:
                raise forms.ValidationError(
                    _(
                        "«Reinvestitsiya» kategoriyasi uchun moliyalashtirish "
                        "«Reinvestitsiya (foydadan)» bo‘lishi kerak."
                    )
                )
            if name.startswith("ta’mir") or name.startswith("ta'mir"):
                if funding != Expense.Funding.OPERATING:
                    raise forms.ValidationError(
                        _(
                            "«Ta’mir (joriy)» kategoriyasi uchun moliyalashtirish "
                            "«Joriy (Sofdan)» bo‘lishi kerak."
                        )
                    )
        return cleaned


class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ("name", "is_active")
        labels = {"name": _("Nomi"), "is_active": _("Faol")}


class VendorForm(forms.ModelForm):
    class Meta:
        model = Vendor
        fields = ("name", "phone", "notes", "is_active")
        labels = {
            "name": _("Nomi"),
            "phone": _("Telefon"),
            "notes": _("Izoh"),
            "is_active": _("Faol"),
        }


class ProfitPartnerForm(forms.ModelForm):
    class Meta:
        model = ProfitPartner
        fields = ("name", "share_percent", "phone", "notes", "is_active")
        labels = {
            "name": _("Ism"),
            "share_percent": _("Ulush %"),
            "phone": _("Telefon"),
            "notes": _("Izoh"),
            "is_active": _("Faol"),
        }

    def clean_share_percent(self):
        value = self.cleaned_data["share_percent"]
        if value is None or value <= 0 or value > 100:
            raise forms.ValidationError(_("Ulush 0 dan katta va 100 dan oshmasin."))
        return value


class ProfitWithdrawalForm(forms.Form):
    partner = forms.ModelChoiceField(queryset=ProfitPartner.objects.none(), label=_("Sherik"))
    amount = forms.DecimalField(min_value=0.01, max_digits=14, decimal_places=2, label=_("Summa"))
    currency = forms.ChoiceField(choices=CURRENCY_CHOICES, label=_("Valyuta"), initial="UZS")
    paid_on = forms.DateField(label=_("Sana"), widget=forms.DateInput(attrs={"type": "date"}))
    payment_method = forms.ChoiceField(
        choices=ProfitWithdrawal.PaymentMethod.choices, label=_("Usul")
    )
    note = forms.CharField(required=False, max_length=255, label=_("Izoh"))
    allow_overdraw = forms.BooleanField(
        required=False,
        label=_("Qoldiqdan ko‘p olishga ruxsat"),
        help_text=_("Moslashuvchan rejim — keyin qayta hisobda ko‘rinadi."),
    )

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["partner"].queryset = ProfitPartner.objects.filter(
                tenant=tenant, is_active=True
            ).order_by("name")
            self.fields["currency"].initial = tenant.currency or "UZS"


class ProfitResetForm(forms.Form):
    ended_on = forms.DateField(
        label=_("Davr tugashi"),
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    restart_today = forms.BooleanField(
        required=False,
        initial=False,
        label=_("Yangi hisobni bugundan boshlash"),
        help_text=_("Belgilanmasa ertasi kundan boshlanadi. Belgilansa shu kun tushumi qayta ulashiladi."),
    )
    note = forms.CharField(required=False, max_length=255, label=_("Izoh"))


class BaseCurrencyForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = ("currency",)
        labels = {"currency": _("Bazaviy valyuta")}
        help_texts = {
            "currency": _(
                "Hisobotlar, P&L va mehmon hisobi qoldig‘i shu valyutada. "
                "USD/EUR to‘lovlar kurs orqali bazaga o‘tkaziladi."
            ),
        }


class ExchangeRateForm(forms.ModelForm):
    class Meta:
        model = ExchangeRate
        fields = ("currency", "rate", "effective_on", "note")
        labels = {
            "currency": _("Valyuta"),
            "rate": _("Kurs (1 birlik → baza)"),
            "effective_on": _("Amal qilish sanasi"),
            "note": _("Izoh"),
        }
        widgets = {"effective_on": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        base = (tenant.currency if tenant else None) or "UZS"
        self.fields["currency"].choices = [
            (c, label) for c, label in CURRENCY_CHOICES if c != base
        ]

    def clean(self):
        cleaned = super().clean()
        if self.tenant and cleaned.get("currency") == self.tenant.currency:
            raise forms.ValidationError(_("Bazaviy valyuta uchun kurs kiritilmaydi."))
        return cleaned
