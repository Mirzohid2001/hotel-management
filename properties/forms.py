from django import forms
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from .models import Floor, Property, PropertySettings, RatePlan, Room, RoomType, SeasonRate


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = ("name", "branch_code", "address", "city", "phone", "email", "is_active")
        labels = {
            "name": _("Nomi"),
            "branch_code": _("Filial kodi"),
            "address": _("Manzil"),
            "city": _("Shahar"),
            "phone": _("Telefon"),
            "email": _("Email"),
            "is_active": _("Faol"),
        }


class PropertySettingsForm(forms.ModelForm):
    class Meta:
        model = PropertySettings
        fields = (
            "tax_percent",
            "early_checkin_fee",
            "late_checkout_fee",
            "emehmon_fee",
            "cancel_fee_percent",
            "no_show_fee_percent",
            "checkin_time",
            "checkout_time",
            "require_id_on_checkin",
        )
        labels = {
            "tax_percent": _("Soliq %"),
            "early_checkin_fee": _("Erta kirish to‘lovi"),
            "late_checkout_fee": _("Kech chiqish to‘lovi"),
            "emehmon_fee": _("E-mehmon (1 mehmon / 1 kecha)"),
            "cancel_fee_percent": _("Bekor qilish %"),
            "no_show_fee_percent": _("Kelmagan % (ishlatilmaydi)"),
            "checkin_time": _("Kirish vaqti"),
            "checkout_time": _("Chiqish vaqti"),
            "require_id_on_checkin": _("Kirishda hujjat talab qilinsin"),
        }
        help_texts = {
            "emehmon_fee": _(
                "E-mehmonga beriladigan komissiya: har bir mehmonning har bir kechasi uchun "
                "(odatda 9000 so‘m). Jami = tarif × kechalar × mehmonlar."
            ),
            "no_show_fee_percent": _(
                "Kelmaganda jarima yozilmaydi — to‘lov avtomatik qaytariladi. Bu maydon saqlanadi, lekin hisobga ta’sir qilmaydi."
            ),
        }


class RoomTypeForm(forms.ModelForm):
    class Meta:
        model = RoomType
        fields = (
            "name",
            "code",
            "capacity_adults",
            "capacity_children",
            "base_price",
            "currency",
            "description",
            "is_active",
        )
        labels = {
            "name": _("Nomi"),
            "code": _("Kod"),
            "capacity_adults": _("Kattalar sig‘imi"),
            "capacity_children": _("Bolalar sig‘imi"),
            "base_price": _("Asosiy narx"),
            "currency": _("Valyuta"),
            "description": _("Tavsif"),
            "is_active": _("Faol"),
        }


class FloorForm(forms.ModelForm):
    class Meta:
        model = Floor
        fields = ("number", "name")
        labels = {"number": _("Raqam"), "name": _("Nomi")}


class RoomTypeQuickForm(forms.Form):
    name = forms.CharField(max_length=120, label=_("Nomi"))
    code = forms.SlugField(
        max_length=40,
        required=False,
        label=_("Kod"),
        help_text=_("Bo‘sh qoldirilsa nomdan yaratiladi."),
    )
    base_price = forms.DecimalField(
        min_value=0,
        max_digits=14,
        decimal_places=2,
        label=_("Asosiy narx"),
        initial=0,
    )
    capacity_adults = forms.IntegerField(
        min_value=1,
        max_value=20,
        label=_("Kattalar"),
        initial=2,
    )


class FloorQuickForm(forms.Form):
    number = forms.IntegerField(label=_("Qavat raqami"))
    name = forms.CharField(max_length=100, required=False, label=_("Nomi"))


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ("room_type", "floor", "number", "status", "notes", "is_active")
        labels = {
            "room_type": _("Xona turi"),
            "floor": _("Qavat"),
            "number": _("Raqam"),
            "status": _("Holat"),
            "notes": _("Izoh"),
            "is_active": _("Faol"),
        }

    def __init__(self, *args, property_obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        if property_obj is not None:
            types = RoomType.objects.filter(property=property_obj, is_active=True)
            if self.instance and self.instance.pk and self.instance.room_type_id:
                types = RoomType.objects.filter(property=property_obj).filter(
                    Q(is_active=True) | Q(pk=self.instance.room_type_id)
                )
            self.fields["room_type"].queryset = types
            self.fields["floor"].queryset = Floor.objects.filter(property=property_obj)
            self.fields["floor"].required = False


class RatePlanForm(forms.ModelForm):
    class Meta:
        model = RatePlan
        fields = (
            "name",
            "code",
            "room_type",
            "price",
            "extra_adult_price",
            "currency",
            "is_default",
            "is_active",
        )
        labels = {
            "name": _("Nomi"),
            "code": _("Kod"),
            "room_type": _("Xona turi"),
            "price": _("Narx"),
            "extra_adult_price": _("Qo‘shimcha katta"),
            "currency": _("Valyuta"),
            "is_default": _("Standart"),
            "is_active": _("Faol"),
        }

    def __init__(self, *args, property_obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        if property_obj is not None:
            types = RoomType.objects.filter(property=property_obj, is_active=True)
            if self.instance and self.instance.pk and self.instance.room_type_id:
                types = RoomType.objects.filter(property=property_obj).filter(
                    Q(is_active=True) | Q(pk=self.instance.room_type_id)
                )
            self.fields["room_type"].queryset = types


class SeasonRateForm(forms.ModelForm):
    class Meta:
        model = SeasonRate
        fields = ("name", "date_from", "date_to", "price")
        labels = {
            "name": _("Nomi"),
            "date_from": _("Boshlanish"),
            "date_to": _("Tugash"),
            "price": _("Narx"),
        }
        widgets = {
            "date_from": forms.DateInput(attrs={"type": "date"}),
            "date_to": forms.DateInput(attrs={"type": "date"}),
        }
