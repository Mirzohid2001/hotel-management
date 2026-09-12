from datetime import timedelta
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.forms import formset_factory
from django.urls import reverse
from django.utils import timezone
from core.currency import CURRENCY_CHOICES
from django.utils.translation import gettext_lazy as _

from guests.models import Company, Guest
from properties.models import PropertySettings, Room, RoomType

from .availability import room_availability_split, walk_in_room_cards
from .commission import active_referrers
from .models import BookingReferrer, ReferrerCommissionPayment, Reservation
from .services import AvailabilityError, assert_room_available, assert_room_physically_free


def _hotel_emehmon_unit(hotel) -> Decimal:
    from folio.services import emehmon_unit_rate

    return emehmon_unit_rate(hotel)


def _add_emehmon_payment_fields(form, *, hotel=None, nights=1, guests=1):
    """Walk-in / zayezd formalariga E-mehmon to‘lov maydonlari."""
    from folio.services import calc_emehmon_fee

    unit = _hotel_emehmon_unit(hotel)
    default_fee = calc_emehmon_fee(unit, nights=nights, guests=guests)
    form.fields["collect_emehmon"] = forms.BooleanField(
        required=False,
        initial=True,
        label=_("E-mehmon komissiyasini olish"),
        help_text=_(
            "Standart: yoqilgan. Hisob = %(u)s so‘m × kechalar × mehmonlar. "
            "O‘chirsangiz — bu mehmondan E-mehmon olinmaydi."
        )
        % {"u": unit if unit > 0 else Decimal("9000")},
    )
    form.fields["emehmon_amount"] = forms.DecimalField(
        required=False,
        min_value=Decimal("0"),
        max_digits=14,
        decimal_places=2,
        label=_("E-mehmon summasi"),
        initial=default_fee if default_fee > 0 else None,
        widget=forms.NumberInput(
            attrs={
                "step": "0.01",
                "min": "0",
                "data-emehmon-unit": str(unit),
            }
        ),
    )
    form.fields["emehmon_method"] = forms.ChoiceField(
        required=False,
        choices=[
            ("cash", _("Naqd")),
            ("card", _("Karta")),
            ("transfer", _("O‘tkazma")),
        ],
        initial="cash",
        label=_("E-mehmon to‘lov usuli"),
    )
    form.emehmon_unit = unit
    form.emehmon_default = default_fee


def _fill_emehmon_amount(form, cleaned, *, nights, guests):
    """Bo‘sh summani avtomatik hisoblash; ixtiyoriy qo‘lda override."""
    from folio.services import calc_emehmon_fee

    if not cleaned.get("collect_emehmon"):
        return cleaned
    amount = cleaned.get("emehmon_amount")
    unit = getattr(form, "emehmon_unit", Decimal("0"))
    if amount is None or amount <= 0:
        computed = calc_emehmon_fee(unit, nights=nights, guests=guests)
        if computed <= 0:
            form.add_error(
                "emehmon_amount",
                _("E-mehmon to‘lovini olish uchun summa kiriting."),
            )
        else:
            cleaned["emehmon_amount"] = computed
    return cleaned


def _hotel_emehmon_default(hotel) -> Decimal:
    """Orqaga moslik — endi 1 kecha × 1 mehmon."""
    from folio.services import calc_emehmon_fee

    return calc_emehmon_fee(_hotel_emehmon_unit(hotel), nights=1, guests=1)


class BookingReferrerForm(forms.ModelForm):
    class Meta:
        model = BookingReferrer
        fields = ("name", "phone", "default_commission_percent", "notes", "is_active")
        labels = {
            "name": _("Ism"),
            "phone": _("Telefon"),
            "default_commission_percent": _("Standart foiz %"),
            "notes": _("Izoh"),
            "is_active": _("Faol"),
        }
        widgets = {
            "default_commission_percent": forms.NumberInput(
                attrs={"step": "0.01", "min": "0", "max": "100"}
            ),
            "notes": forms.TextInput(),
        }
        help_texts = {
            "default_commission_percent": _(
                "Bu odam orqali kelgan mehmonlar uchun odatdagi foiz."
            ),
        }


class BookingReferrerQuickForm(forms.Form):
    name = forms.CharField(max_length=200, label=_("Ism"))
    phone = forms.CharField(required=False, max_length=32, label=_("Telefon"))
    default_commission_percent = forms.DecimalField(
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        decimal_places=2,
        max_digits=5,
        initial=Decimal("15"),
        label=_("Standart foiz %"),
        help_text=_("Bu odam orqali kelgan mehmonlar uchun odatdagi foiz."),
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0", "max": "100"}),
    )


class CommissionPaymentForm(forms.Form):
    amount = forms.DecimalField(
        min_value=Decimal("0.01"),
        max_digits=14,
        decimal_places=2,
        label=_("Summa"),
    )
    currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        label=_("Valyuta"),
        initial="UZS",
        required=False,
    )
    paid_on = forms.DateField(
        label=_("Sana"),
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False,
    )
    method = forms.ChoiceField(
        choices=ReferrerCommissionPayment.Method.choices,
        label=_("Usul"),
        initial=ReferrerCommissionPayment.Method.CASH,
    )
    note = forms.CharField(required=False, max_length=255, label=_("Izoh"))

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        if tenant is not None and not self.is_bound:
            self.fields["currency"].initial = getattr(tenant, "currency", None) or "UZS"
            self.fields["paid_on"].initial = timezone.localdate()

    def clean_currency(self):
        currency = (self.cleaned_data.get("currency") or "").strip().upper()
        if not currency:
            tenant = getattr(self, "tenant", None)
            currency = getattr(tenant, "currency", None) or "UZS"
        if currency not in {c[0] for c in CURRENCY_CHOICES}:
            raise forms.ValidationError(_("Valyuta noto‘g‘ri."))
        return currency


class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = (
            "guest",
            "company",
            "referrer",
            "commission_percent",
            "room_type",
            "room",
            "nightly_rate",
            "currency",
            "check_in",
            "check_out",
            "adults",
            "children",
            "source",
            "status",
            "notes",
        )
        labels = {
            "guest": _("Mehmon"),
            "company": _("Kompaniya"),
            "referrer": _("Kim orqali"),
            "commission_percent": _("Yo‘naltiruvchi foizi %"),
            "room_type": _("Xona turi"),
            "room": _("Xona"),
            "nightly_rate": _("Narx (1 kecha)"),
            "currency": _("Valyuta"),
            "check_in": _("Kirish"),
            "check_out": _("Chiqish"),
            "adults": _("Kattalar"),
            "children": _("Bolalar"),
            "source": _("Manba"),
            "status": _("Holat"),
            "notes": _("Izoh"),
        }
        help_texts = {
            "nightly_rate": _("Kelishilgan bir kechalik summa. Jami = narx × kechalar."),
            "currency": _("Narx shu valyutada — UZS, USD yoki EUR."),
            "check_out": _(
                "Ketish kuni (tushlikgacha). Shu kunga yangi mehmon bron qilish mumkin — "
                "masalan 18→20 bo‘lsa, 20-chi kuni xona bo‘sh."
            ),
        }
        widgets = {
            "check_in": forms.DateInput(attrs={"type": "date"}),
            "check_out": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
            "commission_percent": forms.NumberInput(
                attrs={"step": "0.01", "min": "0", "max": "100"}
            ),
            "nightly_rate": forms.NumberInput(
                attrs={"step": "0.01", "min": "0", "placeholder": "0"}
            ),
        }

    def __init__(self, *args, tenant=None, hotel=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        self.hotel = hotel
        if tenant is not None:
            self.fields["guest"].queryset = Guest.objects.filter(tenant=tenant)
            self.fields["company"].queryset = Company.objects.filter(tenant=tenant, is_active=True)
            self.fields["referrer"].queryset = active_referrers(tenant)
            self.fields["referrer"].required = False
            self.fields["referrer"].empty_label = _("— yo‘q —")
            self.fields["commission_percent"].required = False
            self.fields["commission_percent"].help_text = _(
                "Ixtiyoriy. Faqat «Kim orqali» tanlanganda — shu odamga xona summasidan foiz."
            )
            rooms = Room.objects.filter(
                tenant=tenant, is_active=True, room_type__is_active=True
            )
            room_types = RoomType.objects.filter(tenant=tenant, is_active=True)
            if hotel is not None:
                rooms = rooms.filter(property=hotel)
                room_types = room_types.filter(property=hotel)
            self.fields["room_type"].queryset = room_types
            self.fields["room"].queryset = rooms
            self.fields["company"].required = False
            self.fields["room"].required = False
            self.fields["nightly_rate"].required = True
            self.fields["currency"].choices = CURRENCY_CHOICES
            if not self.is_bound and not self.instance.pk:
                self.fields["currency"].initial = getattr(tenant, "currency", None) or "UZS"
            avail_url = reverse("bookings:availability")
            for name in ("check_in", "check_out", "room", "room_type"):
                self.fields[name].widget.attrs.update(
                    {
                        "hx-get": avail_url,
                        "hx-trigger": "change delay:200ms",
                        "hx-target": "#availability-box",
                        "hx-include": "closest form",
                        "hx-select": "unset",
                        "hx-swap": "outerHTML",
                    }
                )
        if not self.is_bound and not self.instance.pk:
            today = timezone.localdate()
            self.fields["check_in"].initial = today
            self.fields["check_out"].initial = today + timedelta(days=1)

    def clean(self):
        cleaned = super().clean()
        referrer = cleaned.get("referrer")
        percent = cleaned.get("commission_percent")
        if not referrer:
            cleaned["commission_percent"] = None
        elif percent is None:
            cleaned["commission_percent"] = referrer.default_commission_percent
        elif percent < 0 or percent > 100:
            self.add_error("commission_percent", _("Foiz 0–100 oralig‘ida bo‘lishi kerak."))

        nightly = cleaned.get("nightly_rate")
        if nightly is None or nightly <= 0:
            self.add_error("nightly_rate", _("1 kecha narxini kiriting."))

        currency = cleaned.get("currency")
        if not currency:
            room_type = cleaned.get("room_type")
            cleaned["currency"] = (
                getattr(room_type, "currency", None)
                or getattr(self.tenant, "currency", None)
                or "UZS"
            )
        return cleaned


class RoomChoiceField(forms.ModelChoiceField):
    """Xona tanlashda tur ko‘rinsin: 103 · Double · Juftlik."""

    def label_from_instance(self, obj):
        status = obj.get_status_display() if hasattr(obj, "get_status_display") else ""
        type_name = obj.room_type.name if obj.room_type_id else "—"
        if status:
            return f"{obj.number} · {type_name} · {status}"
        return f"{obj.number} · {type_name}"


class ReservationAmendForm(forms.Form):
    check_in = forms.DateField(label=_("Kirish"), widget=forms.DateInput(attrs={"type": "date"}))
    check_out = forms.DateField(
        label=_("Chiqish"),
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text=_(
            "Ketish kuni. Shu kunga keyingi mehmonni bron qilish mumkin (bir kunlik almashuv)."
        ),
    )
    room = RoomChoiceField(
        queryset=Room.objects.none(),
        required=False,
        label=_("Xona"),
        help_text=_("Boshqa turdagi xona tanlansa (masalan Twin↔Double) — tur avtomatik yangilanadi."),
    )
    nightly_rate = forms.DecimalField(
        min_value=Decimal("0.01"),
        max_digits=14,
        decimal_places=2,
        label=_("Narx (1 kecha)"),
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
    )
    currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        label=_("Valyuta"),
        initial="UZS",
    )
    adults = forms.IntegerField(min_value=1, label=_("Kattalar"))
    children = forms.IntegerField(min_value=0, label=_("Bolalar"))
    reason = forms.CharField(required=False, max_length=255, label=_("Sabab"))

    def __init__(self, *args, reservation=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.reservation = reservation
        if reservation is not None:
            self.fields["room"].queryset = (
                Room.objects.filter(
                    tenant=reservation.tenant,
                    property=reservation.hotel,
                    is_active=True,
                    room_type__is_active=True,
                )
                .select_related("room_type")
                .exclude(status=Room.Status.OUT_OF_ORDER)
            )
            self.fields["check_in"].initial = reservation.check_in
            self.fields["check_out"].initial = reservation.check_out
            self.fields["room"].initial = reservation.room_id
            from bookings.services import room_nightly_price

            self.fields["nightly_rate"].initial = (
                reservation.nightly_rate
                if reservation.nightly_rate
                else room_nightly_price(reservation)
            )
            self.fields["currency"].initial = (
                reservation.currency or reservation.tenant.currency or "UZS"
            )
            self.fields["adults"].initial = reservation.adults
            self.fields["children"].initial = reservation.children


class WalkInForm(forms.Form):
    first_name = forms.CharField(
        max_length=120,
        label=_("Ism"),
        widget=forms.TextInput(
            attrs={
                "autofocus": True,
                "placeholder": _("Masalan: Alisher"),
                "autocomplete": "given-name",
            }
        ),
    )
    last_name = forms.CharField(
        required=False,
        max_length=120,
        label=_("Familiya"),
        widget=forms.TextInput(
            attrs={"placeholder": _("Ixtiyoriy"), "autocomplete": "family-name"}
        ),
    )
    phone = forms.CharField(
        required=False,
        max_length=32,
        label=_("Telefon"),
        widget=forms.TextInput(
            attrs={"placeholder": "+998 90 123 45 67", "autocomplete": "tel", "inputmode": "tel"}
        ),
    )
    doc_type = forms.ChoiceField(
        required=False,
        label=_("Hujjat turi"),
        choices=[("", "—"), ("passport", _("Pasport")), ("id_card", _("ID karta"))],
    )
    doc_number = forms.CharField(
        required=False,
        max_length=64,
        label=_("Hujjat raqami"),
        widget=forms.TextInput(attrs={"placeholder": "AA 1234567"}),
    )
    room = forms.ChoiceField(choices=[], label=_("Xona"), widget=forms.HiddenInput())
    nightly_rate = forms.DecimalField(
        min_value=Decimal("0.01"),
        max_digits=14,
        decimal_places=2,
        label=_("Narx (1 kecha)"),
        widget=forms.NumberInput(
            attrs={"step": "0.01", "min": "0", "placeholder": "0"}
        ),
    )
    currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        label=_("Valyuta"),
        initial="UZS",
        help_text=_("Narx shu valyutada — UZS, USD yoki EUR."),
    )
    nights = forms.IntegerField(
        min_value=1,
        initial=1,
        label=_("Tunlar"),
        widget=forms.NumberInput(attrs={"min": 1, "step": 1}),
    )
    adults = forms.IntegerField(
        min_value=1,
        initial=1,
        label=_("Kattalar"),
        widget=forms.NumberInput(attrs={"min": 1, "step": 1}),
    )
    notes = forms.CharField(
        required=False,
        label=_("Izoh"),
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": _("Maxsus so‘rov yoki eslatma")}),
    )
    referrer = forms.ModelChoiceField(
        queryset=BookingReferrer.objects.none(),
        required=False,
        label=_("Kim orqali"),
        empty_label=_("— yo‘q —"),
    )
    commission_percent = forms.DecimalField(
        required=False,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        decimal_places=2,
        max_digits=5,
        label=_("Yo‘naltiruvchi foizi %"),
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0", "max": "100"}),
        help_text=_("Ixtiyoriy. Faqat «Kim orqali» tanlanganda."),
    )

    def __init__(self, *args, tenant=None, hotel=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.hotel = hotel
        self.tenant = tenant
        self.room_cards = []
        self.occupied_rooms = []
        self.available_count = 0
        self.stay_check_in = timezone.localdate()
        self.stay_check_out = self.stay_check_in + timedelta(days=1)
        if tenant is not None:
            self.fields["referrer"].queryset = active_referrers(tenant)
            self.fields["currency"].initial = getattr(tenant, "currency", None) or "UZS"
            nights = self._walk_in_nights()
            today = timezone.localdate()
            check_out = today + timedelta(days=nights)
            self.stay_check_in = today
            self.stay_check_out = check_out
            self.room_cards = walk_in_room_cards(tenant, hotel, today, check_out)
            available, occupied = room_availability_split(
                tenant, hotel, today, check_out
            )
            self.occupied_rooms = occupied
            self.available_count = len(available)

            selectable = [
                c["room"]
                for c in self.room_cards
                if c["state"] in {"free", "dirty"}
            ]
            room_field = self.fields["room"]
            room_field.choices = [(str(r.pk), r.number) for r in selectable]

            self.fields["nights"].widget.attrs.update(
                {
                    "hx-get": reverse("bookings:walk_in_rooms"),
                    "hx-trigger": "change",
                    "hx-target": "#walkin-room-fields",
                    "hx-include": "closest form",
                    "hx-swap": "innerHTML",
                    "hx-select": "unset",
                    "hx-indicator": "#walkin-room-loading",
                }
            )
        nights = self._walk_in_nights()
        adults_initial = 1
        if self.is_bound:
            try:
                adults_initial = max(1, int(self.data.get("adults") or 1))
            except (TypeError, ValueError):
                adults_initial = 1
        _add_emehmon_payment_fields(
            self, hotel=hotel, nights=nights, guests=adults_initial
        )

    def _walk_in_nights(self) -> int:
        if self.is_bound:
            try:
                return max(1, int(self.data.get("nights", 1)))
            except (ValueError, TypeError):
                return 1
        if self.initial.get("nights") is not None:
            try:
                return max(1, int(self.initial["nights"]))
            except (ValueError, TypeError):
                return 1
        return max(1, int(self.fields["nights"].initial or 1))

    def clean(self):
        cleaned = super().clean()
        referrer = cleaned.get("referrer")
        percent = cleaned.get("commission_percent")
        if not referrer:
            cleaned["commission_percent"] = None
        elif percent is None:
            cleaned["commission_percent"] = referrer.default_commission_percent

        nightly = cleaned.get("nightly_rate")
        if nightly is None or nightly <= 0:
            self.add_error("nightly_rate", _("1 kecha narxini kiriting."))

        nights = max(1, int(cleaned.get("nights") or 1))
        guests = max(1, int(cleaned.get("adults") or 1))
        cleaned = _fill_emehmon_amount(self, cleaned, nights=nights, guests=guests)
        return cleaned

    def clean_room(self):
        raw = self.cleaned_data.get("room")
        if not raw:
            raise ValidationError(_("Xona tanlang."))
        try:
            qs = Room.objects.filter(
                tenant=self.tenant, is_active=True, pk=int(raw)
            ).select_related("room_type")
            if self.hotel is not None:
                qs = qs.filter(property=self.hotel)
            room = qs.get()
        except (Room.DoesNotExist, ValueError, TypeError) as exc:
            raise ValidationError(_("Xona topilmadi.")) from exc
        nights = self.cleaned_data.get("nights") or 1
        today = timezone.localdate()
        check_out = today + timedelta(days=nights)
        try:
            assert_room_available(room, today, check_out)
            assert_room_physically_free(room)
        except AvailabilityError as exc:
            raise ValidationError(
                exc.messages[0] if exc.messages else _("Bu xona band — boshqa xona tanlang.")
            ) from exc
        return room


class CalendarQuickBookForm(forms.Form):
    guest = forms.ModelChoiceField(queryset=Guest.objects.none(), label=_("Mehmon"))
    nightly_rate = forms.DecimalField(
        min_value=Decimal("0.01"),
        max_digits=14,
        decimal_places=2,
        label=_("Narx (1 kecha)"),
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
    )
    currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        label=_("Valyuta"),
        initial="UZS",
    )
    adults = forms.IntegerField(min_value=1, initial=2, label=_("Kattalar"))
    status = forms.ChoiceField(
        choices=[
            (Reservation.Status.CONFIRMED, _("Tasdiqlangan")),
            (Reservation.Status.INQUIRY, _("So‘rov")),
        ],
        initial=Reservation.Status.CONFIRMED,
        label=_("Holat"),
    )
    notes = forms.CharField(
        required=False,
        label=_("Izoh"),
        widget=forms.TextInput(attrs={"placeholder": _("Izoh")}),
    )

    def __init__(self, *args, tenant=None, hotel=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["guest"].queryset = Guest.objects.filter(tenant=tenant).order_by(
                "last_name", "first_name"
            )
            if not self.is_bound:
                self.fields["currency"].initial = getattr(tenant, "currency", None) or "UZS"


class TransferForm(forms.Form):
    room_type = forms.ModelChoiceField(
        queryset=RoomType.objects.none(),
        required=False,
        label=_("Kerakli xona turi"),
        help_text=_("Mehmon Twin so‘rasa — Twin ni tanlang; Double↔Twin va boshqalar mumkin."),
        empty_label=_("— barcha turlar —"),
    )
    room = RoomChoiceField(queryset=Room.objects.none(), label=_("Yangi xona"))
    update_rate = forms.BooleanField(
        required=False,
        initial=False,
        label=_("Yangi tur BAR tarifiga o‘tkazish (faqat eski bronlar)"),
    )
    reason = forms.CharField(
        required=False,
        max_length=255,
        label=_("Sabab"),
        widget=forms.TextInput(attrs={"placeholder": _("Masalan: mehmon Twin so‘radi")}),
    )

    def __init__(self, *args, reservation=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.reservation = reservation
        self.room_options = []
        if reservation is not None:
            if reservation.nightly_rate is not None:
                # Qo‘lda narx — tarif checkbox kerak emas
                self.fields["update_rate"].initial = False
                self.fields["update_rate"].widget = forms.HiddenInput()
            types = RoomType.objects.filter(
                tenant=reservation.tenant,
                property=reservation.hotel,
                is_active=True,
            )
            self.fields["room_type"].queryset = types
            rooms = (
                Room.objects.filter(
                    tenant=reservation.tenant,
                    property=reservation.hotel,
                    is_active=True,
                    room_type__is_active=True,
                )
                .select_related("room_type")
                .exclude(pk=reservation.room_id)
                .exclude(status=Room.Status.OUT_OF_ORDER)
                .order_by("number")
            )
            # Faqat sanalar bo‘yicha bo‘sh xonalar
            available_ids = []
            for r in rooms:
                try:
                    assert_room_available(
                        r,
                        reservation.check_in,
                        reservation.check_out,
                        exclude_reservation_id=reservation.pk,
                    )
                    available_ids.append(r.pk)
                except AvailabilityError:
                    continue
            rooms = rooms.filter(pk__in=available_ids)

            selected_type_id = None
            if self.is_bound:
                selected_type_id = self.data.get(self.add_prefix("room_type")) or None
            elif self.initial.get("room_type"):
                selected_type_id = self.initial.get("room_type")
            if selected_type_id:
                rooms = rooms.filter(room_type_id=selected_type_id)
            self.fields["room"].queryset = rooms
            self.room_options = [
                {
                    "id": r.pk,
                    "number": r.number,
                    "type_id": r.room_type_id,
                    "type_name": r.room_type.name,
                    "status": r.get_status_display(),
                    "status_code": r.status,
                }
                for r in (
                    Room.objects.filter(pk__in=available_ids)
                    .select_related("room_type")
                    .order_by("number")
                )
            ]

    def clean(self):
        cleaned = super().clean()
        room = cleaned.get("room")
        room_type = cleaned.get("room_type")
        if room and room_type and room.room_type_id != room_type.id:
            raise ValidationError(
                _("Tanlangan xona «%(room)s» turi «%(got)s», filtr esa «%(want)s».")
                % {
                    "room": room.number,
                    "got": room.room_type.name,
                    "want": room_type.name,
                }
            )
        return cleaned


class GroupBookingForm(forms.Form):
    name = forms.CharField(max_length=200, label=_("Guruh nomi"))
    company = forms.ModelChoiceField(queryset=Company.objects.none(), required=False, label=_("Kompaniya"))
    check_in = forms.DateField(label=_("Kirish"), widget=forms.DateInput(attrs={"type": "date"}))
    check_out = forms.DateField(label=_("Chiqish"), widget=forms.DateInput(attrs={"type": "date"}))
    notes = forms.CharField(required=False, label=_("Izoh"), widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, tenant=None, hotel=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.hotel = hotel
        if tenant is not None:
            self.fields["company"].queryset = Company.objects.filter(tenant=tenant, is_active=True)
        if not self.is_bound:
            today = timezone.localdate()
            self.fields["check_in"].initial = today
            self.fields["check_out"].initial = today + timedelta(days=1)


class GroupRoomForm(forms.Form):
    guest = forms.ModelChoiceField(queryset=Guest.objects.none(), label=_("Mehmon"))
    room_type = forms.ModelChoiceField(queryset=RoomType.objects.none(), label=_("Xona turi"))
    room = forms.ModelChoiceField(queryset=Room.objects.none(), required=False, label=_("Xona"))
    nightly_rate = forms.DecimalField(
        min_value=Decimal("0.01"),
        max_digits=14,
        decimal_places=2,
        label=_("Narx (1 kecha)"),
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
    )
    currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        label=_("Valyuta"),
        initial="UZS",
    )
    adults = forms.IntegerField(min_value=1, initial=1, label=_("Kattalar"))
    children = forms.IntegerField(min_value=0, initial=0, label=_("Bolalar"))

    def __init__(self, *args, tenant=None, hotel=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["guest"].queryset = Guest.objects.filter(tenant=tenant)
            self.fields["currency"].initial = getattr(tenant, "currency", None) or "UZS"
            room_types = RoomType.objects.filter(tenant=tenant, is_active=True)
            rooms = Room.objects.filter(
                tenant=tenant, is_active=True, room_type__is_active=True
            )
            if hotel is not None:
                room_types = room_types.filter(property=hotel)
                rooms = rooms.filter(property=hotel)
            self.fields["room_type"].queryset = room_types
            self.fields["room"].queryset = rooms


def _bind_group_room_form(form, tenant, hotel=None):
    form.fields["guest"].queryset = Guest.objects.filter(tenant=tenant)
    form.fields["currency"].choices = CURRENCY_CHOICES
    if not form.is_bound:
        form.fields["currency"].initial = getattr(tenant, "currency", None) or "UZS"
    room_types = RoomType.objects.filter(tenant=tenant, is_active=True)
    rooms = Room.objects.filter(tenant=tenant, is_active=True, room_type__is_active=True)
    if hotel is not None:
        room_types = room_types.filter(property=hotel)
        rooms = rooms.filter(property=hotel)
    form.fields["room_type"].queryset = room_types
    form.fields["room"].queryset = rooms


def group_room_formset(tenant, data=None, hotel=None):
    FormSet = formset_factory(
        GroupRoomForm,
        extra=0,
        min_num=1,
        validate_min=True,
        can_delete=True,
    )
    fs = FormSet(data, prefix="rooms") if data is not None else FormSet(prefix="rooms")
    for form in fs.forms:
        _bind_group_room_form(form, tenant, hotel)
    _bind_group_room_form(fs.empty_form, tenant, hotel)
    return fs
