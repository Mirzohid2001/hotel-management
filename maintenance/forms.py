from django import forms
from django.utils.translation import gettext_lazy as _

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

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["room"].queryset = Room.objects.filter(tenant=tenant, is_active=True)
            self.fields["room"].required = False
