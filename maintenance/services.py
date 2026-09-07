from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from django.db import transaction
from django.utils import timezone

from housekeeping.services import set_room_status
from properties.models import Room

from .models import MaintenanceTicket


@transaction.atomic
def open_ticket(ticket: MaintenanceTicket) -> MaintenanceTicket:
    ticket.status = MaintenanceTicket.Status.OPEN
    ticket.save(update_fields=["status", "updated_at"])
    if ticket.set_room_ooo and ticket.room_id:
        set_room_status(
            ticket.room,
            Room.Status.OUT_OF_ORDER,
            user=ticket.created_by,
            note=f"Maintenance: {ticket.title}",
        )
    return ticket


@transaction.atomic
def assign_ticket(ticket: MaintenanceTicket, user) -> MaintenanceTicket:
    if ticket.status in {
        MaintenanceTicket.Status.DONE,
        MaintenanceTicket.Status.CANCELLED,
    }:
        raise ValidationError(_("Yopilgan arizaga biriktirib bo‘lmaydi."))
    ticket.assignee = user
    if ticket.status == MaintenanceTicket.Status.OPEN:
        ticket.status = MaintenanceTicket.Status.IN_PROGRESS
        ticket.save(update_fields=["assignee", "status", "updated_at"])
    else:
        ticket.save(update_fields=["assignee", "updated_at"])
    return ticket


@transaction.atomic
def complete_ticket(ticket: MaintenanceTicket, user=None) -> MaintenanceTicket:
    if ticket.status in {
        MaintenanceTicket.Status.DONE,
        MaintenanceTicket.Status.CANCELLED,
    }:
        raise ValidationError(_("Ariza allaqachon yopilgan."))
    ticket.status = MaintenanceTicket.Status.DONE
    ticket.completed_at = timezone.now()
    ticket.save(update_fields=["status", "completed_at", "updated_at"])
    if ticket.set_room_ooo and ticket.room_id and ticket.room.status == Room.Status.OUT_OF_ORDER:
        set_room_status(ticket.room, Room.Status.DIRTY, user=user, note="Maintenance done")
    return ticket
