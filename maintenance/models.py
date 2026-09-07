from django.conf import settings
from django.db import models

from django.utils.translation import gettext_lazy as _
from core.models import TenantOwnedModel
from properties.models import Room


class MaintenanceTicket(TenantOwnedModel):
    class Status(models.TextChoices):
        OPEN = "open", _("Ochiq")
        IN_PROGRESS = "in_progress", _("Jarayonda")
        DONE = "done", _("Bajarilgan")
        CANCELLED = "cancelled", _("Bekor qilingan")

    class Priority(models.TextChoices):
        LOW = "low", _("Past")
        MEDIUM = "medium", _("O‘rtacha")
        HIGH = "high", _("Yuqori")

    room = models.ForeignKey(
        Room, on_delete=models.CASCADE, related_name="maintenance_tickets", null=True, blank=True
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    set_room_ooo = models.BooleanField(
        default=False, help_text="When open, mark room out of order"
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_tickets",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_created",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title
