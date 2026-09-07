from django.conf import settings
from django.db import models

from core.models import TenantOwnedModel


class NightAuditRun(TenantOwnedModel):
    hotel = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="night_audits",
        null=True,
        blank=True,
    )
    audit_date = models.DateField()
    posted_room_charges = models.PositiveIntegerField(default=0)
    open_folios = models.PositiveIntegerField(default=0)
    no_shows_marked = models.PositiveIntegerField(default=0)
    overdue_folios = models.PositiveIntegerField(default=0)
    dirty_rooms = models.PositiveIntegerField(default=0)
    occupancy_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    snapshot = models.JSONField(default=dict, blank=True)
    run_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="night_audits",
    )

    class Meta:
        ordering = ["-audit_date", "-id"]
        unique_together = ("tenant", "hotel", "audit_date")

    def __str__(self) -> str:
        if self.hotel_id:
            return f"Night audit {self.audit_date} · {self.hotel.name}"
        return f"Night audit {self.audit_date}"

    @property
    def is_day_locked(self) -> bool:
        from reports.day_lock import is_property_day_locked

        if self.hotel_id:
            return is_property_day_locked(self.tenant, self.audit_date, self.hotel)
        return False

    @property
    def cod(self) -> dict:
        return (self.snapshot or {}).get("cod") or {}

