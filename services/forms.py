from decimal import Decimal

from django import forms
from django.utils.translation import gettext_lazy as _

from bookings.models import Reservation

from .models import ServiceItem


class ServiceItemForm(forms.ModelForm):
    class Meta:
        model = ServiceItem
        fields = ("name", "code", "unit_price", "currency", "description", "is_active")
        labels = {
            "name": _("Nomi"),
            "code": _("Kod"),
            "unit_price": _("Narx"),
            "currency": _("Valyuta"),
            "description": _("Tavsif"),
            "is_active": _("Faol"),
        }


class ServiceOrderForm(forms.Form):
    reservation = forms.ModelChoiceField(queryset=Reservation.objects.none(), label=_("Bron"))
    service = forms.ModelChoiceField(queryset=ServiceItem.objects.none(), label=_("Xizmat"))
    quantity = forms.DecimalField(min_value=Decimal("0.01"), initial=Decimal("1"), label=_("Miqdor"))
    note = forms.CharField(required=False, max_length=255, label=_("Izoh"))

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["reservation"].queryset = Reservation.objects.filter(
                tenant=tenant, status=Reservation.Status.CHECKED_IN
            ).select_related("guest")
            self.fields["service"].queryset = ServiceItem.objects.filter(tenant=tenant, is_active=True)
