from django.forms.widgets import Select
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _


class SearchableSelect(Select):
    """Native <select> plus type-to-filter combobox UI (see searchable-select.js)."""

    def __init__(self, attrs=None, choices=(), *, search_placeholder=None):
        self.search_placeholder = search_placeholder or _("Ism bo‘yicha qidirish…")
        attrs = dict(attrs or {})
        css = attrs.get("class", "")
        attrs["class"] = f"{css} searchable-select-native".strip()
        attrs["data-searchable-native"] = "1"
        super().__init__(attrs=attrs, choices=choices)

    def render(self, name, value, attrs=None, renderer=None):
        select_html = super().render(name, value, attrs=attrs, renderer=renderer)
        return format_html(
            '<div class="searchable-select" data-searchable-select>'
            '<input type="search" class="searchable-select-query" placeholder="{}" '
            'autocomplete="off" spellcheck="false" aria-autocomplete="list" '
            'aria-label="{}" />'
            "{}"
            '<ul class="searchable-select-menu" role="listbox" hidden></ul>'
            "</div>",
            self.search_placeholder,
            self.search_placeholder,
            select_html,
        )
