from django.db import transaction
from django.utils import timezone

from core.models import log_activity
from properties.models import Room

from .models import HousekeepingTask, RoomStatusLog


@transaction.atomic
def set_room_status(room: Room, new_status: str, user=None, note="") -> Room:
    old = room.status
    if old == new_status:
        return room
    room.status = new_status
    room.save(update_fields=["status", "updated_at"])
    RoomStatusLog.objects.create(
        tenant=room.tenant,
        room=room,
        old_status=old,
        new_status=new_status,
        user=user,
        note=note,
    )
    return room


@transaction.atomic
def assign_task(task: HousekeepingTask, user) -> HousekeepingTask:
    task.assigned_to = user
    if task.status == HousekeepingTask.Status.PENDING:
        task.status = HousekeepingTask.Status.IN_PROGRESS
        task.save(update_fields=["assigned_to", "status", "updated_at"])
    else:
        task.save(update_fields=["assigned_to", "updated_at"])
    return task


@transaction.atomic
def complete_task(task: HousekeepingTask, user=None) -> HousekeepingTask:
    task.status = HousekeepingTask.Status.DONE
    task.completed_at = timezone.now()
    if user is not None and task.assigned_to_id is None:
        task.assigned_to = user
        task.save(update_fields=["status", "completed_at", "assigned_to", "updated_at"])
    else:
        task.save(update_fields=["status", "completed_at", "updated_at"])
    set_room_status(task.room, Room.Status.READY, user=user, note="HK done")
    log_activity(
        tenant=task.tenant,
        user=user,
        action="hk_task_done",
        model="HousekeepingTask",
        object_id=task.pk,
        payload={"room": task.room.number, "title": task.title},
    )
    return task
