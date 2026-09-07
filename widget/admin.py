from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import WidgetConfig


class WidgetConfigInline(admin.StackedInline):
    model = WidgetConfig
    extra = 0
    max_num = 1
    can_delete = False
    fk_name = "hotel"
    readonly_fields = ("public_key", "embed_preview", "embed_iframe_preview")
    fields = (
        "is_enabled",
        "allowed_domains",
        "auto_confirm",
        "auto_assign_room",
        "welcome_title",
        "welcome_text",
        "public_key",
        "embed_iframe_preview",
        "embed_preview",
    )

    @admin.display(description=_("Iframe embed"))
    def embed_iframe_preview(self, obj: WidgetConfig):
        if not obj.pk:
            return "—"
        return format_html(
            '<textarea rows="4" style="width:100%;font-family:monospace" readonly>{}</textarea>',
            obj.embed_iframe_html,
        )

    @admin.display(description=_("Script embed"))
    def embed_preview(self, obj: WidgetConfig):
        if not obj.pk:
            return "—"
        return format_html(
            '<textarea rows="3" style="width:100%;font-family:monospace" readonly>{}</textarea>',
            obj.embed_script_html,
        )


@admin.register(WidgetConfig)
class WidgetConfigAdmin(admin.ModelAdmin):
    list_display = ("hotel", "tenant", "is_enabled", "updated_at")
    list_filter = ("is_enabled", "tenant")
    search_fields = ("tenant__name", "hotel__name", "allowed_domains")
    autocomplete_fields = ("tenant", "hotel")
    readonly_fields = ("public_key", "embed_preview", "embed_iframe_preview", "created_at", "updated_at")

    @admin.display(description=_("Iframe"))
    def embed_iframe_preview(self, obj: WidgetConfig):
        return format_html(
            '<textarea rows="4" style="width:100%;font-family:monospace" readonly>{}</textarea>',
            obj.embed_iframe_html,
        )

    @admin.display(description=_("Script"))
    def embed_preview(self, obj: WidgetConfig):
        return format_html(
            '<textarea rows="3" style="width:100%;font-family:monospace" readonly>{}</textarea>',
            obj.embed_script_html,
        )
