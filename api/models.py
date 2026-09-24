import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


def generate_api_token() -> str:
    return secrets.token_urlsafe(32)


class ApiToken(models.Model):
    """Bearer token for mobile / API clients (web sessions unchanged)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_tokens",
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="api_tokens",
        help_text="Default tenant bound to this token.",
    )
    key = models.CharField(max_length=64, unique=True, db_index=True, default=generate_api_token)
    label = models.CharField(max_length=64, blank=True, default="mobile")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user_id}@{self.tenant_id} ({self.label})"

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    def touch(self):
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at"])

    def revoke(self):
        self.revoked_at = timezone.now()
        self.save(update_fields=["revoked_at"])
