from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "16. Jurnal · Журнал"

    def ready(self):
        from .admin_branding import configure_admin

        configure_admin()
