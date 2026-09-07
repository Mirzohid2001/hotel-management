from django.apps import AppConfig


class WidgetConfigApp(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "widget"
    verbose_name = "Veb-bron widget"

    def ready(self):
        from . import signals  # noqa: F401
