from django import forms
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from core.currency import CURRENCY_CHOICES
from finance.models import Expense
from properties.models import Room

from .models import MaintenanceTicket


class MaintenanceTicketForm(forms.ModelForm):
    class Meta:
        model = MaintenanceTicket
        fields = ("room", "title", "description", "priority", "set_room_ooo")
        labels = {
            "room": _("Xona"),
            "title": _("Sarlavha"),
            "description": _("Tavsif"),
            "priority": _("Muhimlik"),
            "set_room_ooo": _("Xonani nosoz qilish"),
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, tenant=None, hotel=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            rooms = Room.objects.filter(tenant=tenant, is_active=True)
            if hotel is not None:
                rooms = rooms.filter(property=hotel)
            self.fields["room"].queryset = rooms.order_by("number")
            self.fields["room"].required = False


class MaintenanceSpendForm(forms.Form):
    title = forms.CharField(max_length=200, label=_("Nima uchun"))
    amount = forms.DecimalField(
        min_value=0.01, max_digits=14, decimal_places=2, label=_("Summa")
    )
    currency = forms.ChoiceField(choices=CURRENCY_CHOICES, label=_("Valyuta"), initial="UZS")
    expense_date = forms.DateField(
        label=_("Sana"), widget=forms.DateInput(attrs={"type": "date"})
    )
    funding = forms.ChoiceField(
        choices=Expense.Funding.choices,
        label=_("Qayerdan"),
        initial=Expense.Funding.OPERATING,
        help_text=_(
            "Joriy — Sofdan. Reinvestitsiya — Sofga tegmaydi, uchreditel foydasidan."
        ),
    )
    payment_method = forms.ChoiceField(
        choices=Expense.PaymentMethod.choices, label=_("To‘lov usuli")
    )
    ticket = forms.ModelChoiceField(
        queryset=MaintenanceTicket.objects.none(),
        required=False,
        label=_("Ariza (ixtiyoriy)"),
    )
    notes = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}), label=_("Izoh")
    )

    def __init__(self, *args, tenant=None, hotel=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["currency"].initial = tenant.currency or "UZS"
            tickets = MaintenanceTicket.objects.filter(
                tenant=tenant,
                status__in=[
                    MaintenanceTicket.Status.OPEN,
                    MaintenanceTicket.Status.IN_PROGRESS,
                    MaintenanceTicket.Status.DONE,
                ],
            ).order_by("-created_at")
            if hotel is not None:
                tickets = tickets.filter(
                    Q(room__property=hotel) | Q(room__isnull=True)
                ).distinct()
            self.fields["ticket"].queryset = tickets
            self.fields["ticket"].required = False
