from decimal import Decimal

from django import forms
from django.utils.translation import gettext_lazy as _

from core.currency import CURRENCY_CHOICES, get_rate_to_base
from .models import FolioCharge, GuestPayment


class ChargeForm(forms.Form):
    charge_type = forms.ChoiceField(choices=FolioCharge.ChargeType.choices, label=_("Xarajat turi"))
    description = forms.CharField(
        max_length=255,
        label=_("Nima uchun"),
        widget=forms.TextInput(attrs={"placeholder": _("Masalan: kechki ovqat, shikast")}),
    )
    quantity = forms.DecimalField(min_value=Decimal("0.01"), initial=Decimal("1"), label=_("Miqdor"))
    unit_price = forms.DecimalField(
        min_value=Decimal("0"),
        label=_("Birlik narxi"),
        widget=forms.NumberInput(attrs={"step": "0.01", "placeholder": "0"}),
    )
    currency = forms.ChoiceField(choices=CURRENCY_CHOICES, label=_("Valyuta"), initial="UZS")


class PaymentForm(forms.Form):
    method = forms.ChoiceField(choices=GuestPayment.Method.choices, label=_("To‘lov usuli"))
    kind = forms.ChoiceField(
        choices=[
            (GuestPayment.Kind.PAYMENT, _("To‘lov")),
            (GuestPayment.Kind.DEPOSIT, _("Depozit")),
        ],
        initial=GuestPayment.Kind.PAYMENT,
        label=_("To‘lov turi"),
    )
    amount = forms.DecimalField(
        min_value=Decimal("0.01"),
        label=_("Summa"),
        widget=forms.NumberInput(attrs={"step": "0.01", "autofocus": True, "placeholder": "0"}),
    )
    currency = forms.ChoiceField(choices=CURRENCY_CHOICES, label=_("Valyuta"), initial="UZS")
    note = forms.CharField(
        required=False,
        max_length=255,
        label=_("Izoh"),
        widget=forms.TextInput(attrs={"placeholder": _("Ixtiyoriy")}),
    )

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        if tenant is not None:
            self.fields["currency"].initial = tenant.currency or "UZS"


class RefundForm(forms.Form):
    """Ortib qolgan pulni (sdachi) qaytarish."""

    method = forms.ChoiceField(
        choices=GuestPayment.Method.choices,
        initial=GuestPayment.Method.CASH,
        label=_("Qaytarish usuli"),
    )
    amount = forms.DecimalField(
        min_value=Decimal("0.01"),
        label=_("Summa"),
        widget=forms.NumberInput(attrs={"step": "0.01", "autofocus": True}),
    )
    currency = forms.ChoiceField(choices=CURRENCY_CHOICES, label=_("Valyuta"), initial="UZS")
    note = forms.CharField(
        required=False,
        max_length=255,
        label=_("Izoh"),
        widget=forms.TextInput(attrs={"placeholder": _("Masalan: sdachi naqd")}),
    )

    def __init__(self, *args, tenant=None, max_amount=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        # max_amount — bazaviy valyutadagi credit (folio.credit_amount)
        self.max_amount = max_amount
        if tenant is not None:
            self.fields["currency"].initial = tenant.currency or "UZS"
        if max_amount is not None and max_amount > 0:
            self.fields["amount"].initial = max_amount
            self.fields["amount"].help_text = _(
                "Maksimal avans: %(m)s %(cur)s (bazaviy). Boshqa valyutada kurs bo‘yicha hisoblanadi."
            ) % {"m": max_amount, "cur": (tenant.currency if tenant else "UZS") or "UZS"}

    def clean(self):
        cleaned = super().clean()
        amount = cleaned.get("amount")
        currency = cleaned.get("currency")
        if (
            amount is not None
            and self.max_amount is not None
            and self.tenant is not None
        ):
            from core.currency import to_base_amount

            _cur, _rate, amount_base = to_base_amount(self.tenant, amount, currency)
            if amount_base > self.max_amount:
                raise forms.ValidationError(
                    _("Ortganidan ko‘p: maksimal %(m)s %(cur)s.")
                    % {
                        "m": self.max_amount,
                        "cur": self.tenant.currency or "UZS",
                    }
                )
        return cleaned


class VoidForm(forms.Form):
    reason = forms.CharField(max_length=255, min_length=3, label=_("Sabab"))


class CityLedgerTransferForm(forms.Form):
    charge_ids = forms.TypedMultipleChoiceField(
        coerce=int,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label=_("Yozuvlar"),
    )
    transfer_all = forms.BooleanField(required=False, initial=False, label=_("Hammasi"))
    notes = forms.CharField(required=False, max_length=255, label=_("Izoh"))

    def __init__(self, *args, folio=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.folio = folio
        if folio is not None:
            choices = [
                (c.pk, f"{c.get_charge_type_display()}: {c.description} ({c.amount})")
                for c in folio.charges.filter(is_void=False)
            ]
            self.fields["charge_ids"].choices = choices

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("transfer_all"):
            return cleaned
        if not cleaned.get("charge_ids"):
            raise forms.ValidationError(_("Yozuvlarni tanlang yoki hammasi belgilang."))
        return cleaned


class CompanyPaymentForm(forms.Form):
    method = forms.ChoiceField(choices=GuestPayment.Method.choices, label=_("Usul"))
    amount = forms.DecimalField(min_value=Decimal("0.01"), label=_("Summa"))
    currency = forms.ChoiceField(choices=CURRENCY_CHOICES, label=_("Valyuta"), initial="UZS")
    note = forms.CharField(required=False, max_length=255, label=_("Izoh"))

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["currency"].initial = tenant.currency or "UZS"


class StayServiceForm(forms.Form):
    service = forms.ModelChoiceField(queryset=None, label=_("Xizmat"))
    quantity = forms.DecimalField(min_value=Decimal("0.01"), initial=Decimal("1"), label=_("Miqdor"))
    note = forms.CharField(required=False, max_length=255, label=_("Izoh"))

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        from services.models import ServiceItem

        qs = ServiceItem.objects.none()
        if tenant is not None:
            qs = ServiceItem.objects.filter(tenant=tenant, is_active=True)
        self.fields["service"].queryset = qs


class StayMinibarForm(forms.Form):
    item = forms.ModelChoiceField(queryset=None, label=_("Mahsulot"))
    quantity = forms.DecimalField(min_value=Decimal("0.01"), initial=Decimal("1"), label=_("Miqdor"))

    def __init__(self, *args, tenant=None, hotel=None, **kwargs):
        super().__init__(*args, **kwargs)
        from inventory.models import StockItem

        qs = StockItem.objects.none()
        if tenant is not None:
            qs = StockItem.objects.filter(tenant=tenant, is_active=True, is_minibar=True)
            if hotel is not None:
                qs = qs.filter(hotel=hotel)
        self.fields["item"].queryset = qs


class SplitPaymentForm(forms.Form):
    """Bo‘lingan to‘lov: dinamik qatorlar (method/amount/kind list)."""

    note = forms.CharField(required=False, max_length=255, label=_("Izoh"))

    MAX_LINES = 10

    @staticmethod
    def _getlist(raw, key):
        if hasattr(raw, "getlist"):
            return list(raw.getlist(key))
        val = raw.get(key) if raw is not None else None
        if val is None:
            return []
        if isinstance(val, (list, tuple)):
            return list(val)
        return [val]

    def clean(self):
        cleaned = super().clean()
        raw = self.data
        methods = self._getlist(raw, "method")
        amounts = self._getlist(raw, "amount")
        kinds = self._getlist(raw, "kind")
        currencies = self._getlist(raw, "currency")
        n = max(len(methods), len(amounts), len(kinds), len(currencies))
        if n > self.MAX_LINES:
            raise forms.ValidationError(
                _("Ko‘pi bilan %(n)s ta to‘lov qatori.") % {"n": self.MAX_LINES}
            )
        method_values = {c.value for c in GuestPayment.Method}
        kind_values = {c.value for c in GuestPayment.Kind}
        currency_values = {c[0] for c in CURRENCY_CHOICES}
        lines = []
        for i in range(n):
            amount_raw = amounts[i] if i < len(amounts) else ""
            if amount_raw in (None, ""):
                continue
            try:
                amount = Decimal(str(amount_raw).replace(",", "."))
            except Exception:
                raise forms.ValidationError(_("Summa noto‘g‘ri."))
            if amount <= 0:
                continue
            method = methods[i] if i < len(methods) else GuestPayment.Method.CASH
            kind = kinds[i] if i < len(kinds) else GuestPayment.Kind.PAYMENT
            currency = currencies[i] if i < len(currencies) else "UZS"
            if method not in method_values:
                method = GuestPayment.Method.CASH
            if kind not in kind_values:
                kind = GuestPayment.Kind.PAYMENT
            if currency not in currency_values:
                currency = "UZS"
            lines.append(
                {
                    "amount": amount,
                    "method": method,
                    "kind": kind,
                    "currency": currency,
                    "note": cleaned.get("note") or "",
                }
            )
        if not lines:
            raise forms.ValidationError(_("Kamida bitta musbat summali to‘lov qo‘shing."))
        cleaned["lines"] = lines
        return cleaned

    def lines(self):
        return self.cleaned_data.get("lines") or []


class OpenShiftForm(forms.Form):
    opening_float = forms.DecimalField(
        min_value=Decimal("0"),
        initial=Decimal("0"),
        label=_("Boshlang‘ich kassa"),
        help_text=_("Smena boshida qutidagi naqd pul."),
        widget=forms.NumberInput(
            attrs={"step": "0.01", "inputmode": "decimal", "placeholder": "0", "autofocus": True}
        ),
    )


class CloseShiftForm(forms.Form):
    closing_cash = forms.DecimalField(
        min_value=Decimal("0"),
        label=_("Sanab chiqilgan naqd"),
        help_text=_("Kassani sanab, haqiqiy summani kiriting."),
        widget=forms.NumberInput(
            attrs={
                "step": "0.01",
                "inputmode": "decimal",
                "placeholder": "0",
                "data-close-cash": "1",
            }
        ),
    )
    notes = forms.CharField(
        required=False,
        label=_("Topshirish izohi"),
        widget=forms.Textarea(
            attrs={"rows": 2, "placeholder": _("Farq sababi, keyingi smenaga izoh…")}
        ),
    )


class CashMovementForm(forms.Form):
    kind = forms.ChoiceField(
        choices=[
            ("pay_in", _("Kassa kirim (qo‘shimcha naqd)")),
            ("pay_out", _("Kassa chiqim (mayda xarajat / olib ketish)")),
        ],
        label=_("Turi"),
        widget=forms.Select(attrs={"data-movement-kind": "1"}),
    )
    amount = forms.DecimalField(
        min_value=Decimal("0.01"),
        label=_("Summa"),
        widget=forms.NumberInput(
            attrs={"step": "0.01", "inputmode": "decimal", "placeholder": "0"}
        ),
    )
    currency = forms.ChoiceField(choices=CURRENCY_CHOICES, label=_("Valyuta"), initial="UZS")
    note = forms.CharField(
        required=False,
        max_length=255,
        label=_("Izoh"),
        widget=forms.TextInput(attrs={"placeholder": _("Masalan: mayda valyuta, kuryer…")}),
    )

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["currency"].initial = tenant.currency or "UZS"
