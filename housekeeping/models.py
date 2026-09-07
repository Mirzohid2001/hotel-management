from django.conf import settings
from django.db import models

from django.utils.translation import gettext_lazy as _
from core.models import TenantOwnedModel
from properties.models import Room


class HousekeepingTask(TenantOwnedModel):
    class Status(models.TextChoices):
        PENDING = "pending", _("Kutilmoqda")
        IN_PROGRESS = "in_progress", _("Jarayonda")
        DONE = "done", _("Bajarilgan")

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="hk_tasks")
    title = models.CharField(max_length=200, default="Cleaning")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hk_tasks",
    )
    notes = models.CharField(max_length=255, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.room.number}: {self.title}"


class RoomStatusLog(TenantOwnedModel):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="status_logs")
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="room_status_logs",
    )
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
