from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from bookings.models import Reservation

from .images import (
    _PHOTO_MAX_COUNT,
    collect_uploads,
    normalize_stock_image,
    validate_stock_photo,
)
from .models import StockItem, StockMovement


class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True


class MultiplePhotoField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "widget",
            MultipleFileInput(
                attrs={
                    "accept": "image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif",
                    "multiple": True,
                }
            ),
        )
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        files = collect_uploads(data)
        if not files:
            if self.required:
                raise ValidationError(self.error_messages["required"], code="required")
            return []
        if len(files) > _PHOTO_MAX_COUNT:
            raise ValidationError(_("Bir mahsulotga %(n)s tadan ko‘p rasm yuklanmaydi.") % {"n": _PHOTO_MAX_COUNT})
        cleaned = []
        for upload in files:
            validate_stock_photo(upload)
            cleaned.append(normalize_stock_image(upload))
        return cleaned


class StockItemForm(forms.ModelForm):
    photos = MultiplePhotoField(
        required=False,
        label=_("Rasmlar"),
        help_text=_("Ixtiyoriy. Bir nechta rasm: JPG, PNG, WEBP yoki iPhone HEIC, har biri 8 MB gacha."),
    )

    class Meta:
        model = StockItem
        fields = (
            "name",
            "sku",
            "unit",
            "quantity_on_hand",
            "reorder_level",
            "unit_cost",
            "sell_price",
            "currency",
            "expiry_date",
            "expiry_alert_days",
            "is_minibar",
            "is_active",
        )
        labels = {
            "name": _("Nomi"),
            "sku": _("SKU"),
            "unit": _("Birlik"),
            "quantity_on_hand": _("Qoldiq"),
            "reorder_level": _("Minimal qoldiq"),
            "unit_cost": _("Tannarx"),
            "sell_price": _("Sotish narxi"),
            "currency": _("Valyuta"),
            "expiry_date": _("Yaroqlilik muddati"),
            "expiry_alert_days": _("Ogohlantirish (kun)"),
            "is_minibar": _("Minibar"),
            "is_active": _("Faol"),
        }
        help_texts = {
            "expiry_date": _("Masalan: sut, sharbat. Bo‘sh = muddat yo‘q."),
            "expiry_alert_days": _("Standart 7 kun oldin ogohlantiradi."),
        }
        widgets = {
            "unit": forms.Select,
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
            "expiry_alert_days": forms.NumberInput(attrs={"min": 0, "max": 365}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(
            [
                "name",
                "sku",
                "photos",
                "unit",
                "quantity_on_hand",
                "reorder_level",
                "unit_cost",
                "sell_price",
                "currency",
                "expiry_date",
                "expiry_alert_days",
                "is_minibar",
                "is_active",
            ]
        )


class StockAdjustForm(forms.Form):
    movement_type = forms.ChoiceField(choices=StockMovement.MovementType.choices, label=_("Harakat"))
    quantity = forms.DecimalField(min_value=Decimal("0.01"), label=_("Miqdor"))
    note = forms.CharField(required=False, max_length=255, label=_("Izoh"))


class MinibarQuickForm(forms.Form):
    room_number = forms.CharField(
        max_length=32,
        label=_("Xona raqami"),
        widget=forms.TextInput(attrs={"placeholder": _("101"), "autofocus": True}),
    )
    item = forms.ModelChoiceField(queryset=StockItem.objects.none(), label=_("Mahsulot"))
    quantity = forms.DecimalField(min_value=Decimal("0.01"), initial=Decimal("1"), label=_("Miqdor"))

    def __init__(self, *args, tenant=None, hotel=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        self.hotel = hotel
        if tenant is not None:
            items = StockItem.objects.filter(tenant=tenant, is_active=True, is_minibar=True)
            if hotel is not None:
                items = items.filter(hotel=hotel)
            self.fields["item"].queryset = items

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        from properties.models import Room

        room_qs = Room.objects.filter(
            tenant=self.tenant,
            number__iexact=cleaned["room_number"].strip(),
            is_active=True,
        )
        if self.hotel is not None:
            room_qs = room_qs.filter(property=self.hotel)
        room = room_qs.first()
        if room is None:
            raise forms.ValidationError(_("Xona topilmadi."))
        reservation = Reservation.objects.filter(
            tenant=self.tenant,
            room=room,
            status=Reservation.Status.CHECKED_IN,
        ).first()
        if reservation is None:
            raise forms.ValidationError(_("Bu xonada yashovchi mehmon yo‘q."))
        cleaned["reservation"] = reservation
        cleaned["room"] = room
        return cleaned


class MinibarItemQuickForm(forms.Form):
    """Tez minibar mahsuloti — sotuv sahifasidan."""

    name = forms.CharField(max_length=200, label=_("Nomi"))
    sell_price = forms.DecimalField(
        min_value=Decimal("0"),
        max_digits=14,
        decimal_places=2,
        label=_("Sotish narxi"),
    )
    quantity_on_hand = forms.DecimalField(
        min_value=Decimal("0"),
        max_digits=12,
        decimal_places=2,
        initial=Decimal("10"),
        required=False,
        label=_("Qoldiq"),
    )
    sku = forms.CharField(
        max_length=80,
        required=False,
        label=_("SKU"),
        help_text=_("Bo‘sh qoldirilsa avtomatik yaratiladi."),
    )
    photos = MultiplePhotoField(
        required=False,
        label=_("Rasmlar"),
        help_text=_("Ixtiyoriy. Bir nechta rasm: JPG, PNG, WEBP yoki iPhone HEIC."),
    )


class MinibarSaleForm(forms.Form):
    reservation = forms.ModelChoiceField(queryset=Reservation.objects.none(), label=_("Bron"))
    item = forms.ModelChoiceField(queryset=StockItem.objects.none(), label=_("Mahsulot"))
    quantity = forms.DecimalField(min_value=Decimal("0.01"), initial=Decimal("1"), label=_("Miqdor"))

    def __init__(self, *args, tenant=None, hotel=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            res_qs = Reservation.objects.filter(
                tenant=tenant, status=Reservation.Status.CHECKED_IN
            )
            items = StockItem.objects.filter(tenant=tenant, is_active=True, is_minibar=True)
            if hotel is not None:
                res_qs = res_qs.filter(hotel=hotel)
                items = items.filter(hotel=hotel)
            self.fields["reservation"].queryset = res_qs
            self.fields["item"].queryset = items
