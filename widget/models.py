import secrets
from urllib.parse import urlparse

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class WidgetConfig(models.Model):
    """Har bir filial uchun alohida veb-bron widget."""

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="widget_configs",
    )
    hotel = models.OneToOneField(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="widget_config",
        verbose_name=_("Filial"),
    )
    is_enabled = models.BooleanField(default=False, verbose_name=_("Widget yoqilgan"))
    allowed_domains = models.TextField(
        blank=True,
        verbose_name=_("Ruxsat etilgan domenlar"),
        help_text=_("Har qator: aida-hotel.uz"),
    )
    public_key = models.CharField(max_length=64, unique=True, editable=False)
    auto_confirm = models.BooleanField(default=False, verbose_name=_("Avtomatik tasdiqlash"))
    auto_assign_room = models.BooleanField(default=True, verbose_name=_("Xona biriktirish"))
    welcome_title = models.CharField(max_length=200, blank=True, default="")
    welcome_text = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Veb-bron widget")
        verbose_name_plural = _("Veb-bron widgetlar")

    def __str__(self) -> str:
        return f"Widget · {self.hotel.name}"

    def save(self, *args, **kwargs):
        if not self.public_key:
            self.public_key = secrets.token_urlsafe(24)
        if self.tenant_id is None and self.hotel_id:
            self.tenant_id = self.hotel.tenant_id
        super().save(*args, **kwargs)

    def domain_list(self) -> list[str]:
        rows = []
        for line in self.allowed_domains.splitlines():
            line = line.strip().lower()
            if not line:
                continue
            if "://" in line:
                line = urlparse(line).netloc or line
            line = line.split("/")[0].split(":")[0]
            line = line.removeprefix("www.")
            if line:
                rows.append(line)
        return rows

    def referer_allowed(self, referer: str) -> bool:
        domains = self.domain_list()
        if not domains:
            return True
        if not referer:
            return True
        try:
            host = urlparse(referer).netloc.lower().removeprefix("www.")
        except Exception:
            return False
        if not host:
            return True
        return host in domains

    def origin_allowed(self, origin: str) -> bool:
        if not origin or origin == "null":
            return self.referer_allowed("")
        return self.referer_allowed(origin)

    @property
    def widget_path(self) -> str:
        return f"/widget/{self.tenant.slug}/{self.hotel.branch_code}/"

    @property
    def embed_iframe_html(self) -> str:
        base = getattr(settings, "WIDGET_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
        return (
            f'<iframe src="{base}{self.widget_path}" '
            f'title="{self.hotel.name} — onlayn bron" '
            f'style="width:100%;min-height:720px;border:0;border-radius:12px" '
            f'loading="lazy"></iframe>'
        )

    @property
    def embed_script_html(self) -> str:
        base = getattr(settings, "WIDGET_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
        return (
            f'<script src="{base}/static/widget/embed.js" '
            f'data-hotel="{self.tenant.slug}" '
            f'data-branch="{self.hotel.branch_code}" '
            f'data-base="{base}" defer></script>'
        )
