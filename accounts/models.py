from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Platform user; hotel access is via TenantMembership."""

    phone = models.CharField(max_length=32, blank=True)

    class Meta:
        ordering = ["username"]

    def __str__(self) -> str:
        return self.get_full_name() or self.username
