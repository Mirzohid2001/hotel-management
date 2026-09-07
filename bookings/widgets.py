from django import forms
from django.utils.translation import gettext as _


class WalkInRoomSelect(forms.Select):
    """Band xonalarni disabled va «Band» yorlig'i bilan ko'rsatadi."""

    def __init__(self, *, occupied_ids=None, **kwargs):
        self.occupied_ids = {int(x) for x in (occupied_ids or [])}
        super().__init__(**kwargs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs
        )
        if value:
            try:
                if int(value) in self.occupied_ids:
                    option["attrs"]["disabled"] = True
                    option["label"] = f"{label} — {_('Band')}"
            except (ValueError, TypeError):
                pass
        return option
