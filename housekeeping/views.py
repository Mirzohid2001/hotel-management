from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.mixins import feature_required, role_required
from core.roles import HOUSEKEEPING
from core.staff import tenant_staff_users
from properties.models import Room

from .models import HousekeepingTask
from .services import assign_task, complete_task, set_room_status

User = get_user_model()


def _hk_staff(tenant):
    return tenant_staff_users(tenant)


@feature_required("housekeeping")
@role_required(*HOUSEKEEPING)
def hk_board(request):
    rooms = Room.objects.filter(tenant=request.tenant, is_active=True).order_by("number")
    hotel = getattr(request, "active_property", None)
    if hotel is not None:
        rooms = rooms.filter(property=hotel)
    room_list = list(rooms)
    hk_stats = {
        "total": len(room_list),
        "ready": 0,
        "dirty": 0,
        "cleaning": 0,
        "ooo": 0,
        "tasks": 0,
    }
    for room in room_list:
        if room.status == Room.Status.READY:
            hk_stats["ready"] += 1
        elif room.status == Room.Status.DIRTY:
            hk_stats["dirty"] += 1
        elif room.status in (Room.Status.CLEANING, Room.Status.INSPECTED):
            hk_stats["cleaning"] += 1
        elif room.status == Room.Status.OUT_OF_ORDER:
            hk_stats["ooo"] += 1
    tasks = HousekeepingTask.objects.filter(
        tenant=request.tenant, status__in=["pending", "in_progress"]
    ).select_related("room", "assigned_to")
    if hotel is not None:
        tasks = tasks.filter(room__property=hotel)
    hk_stats["tasks"] = tasks.count()
    return render(
        request,
        "housekeeping/board.html",
        {
            "rooms": room_list,
            "tasks": tasks,
            "statuses": Room.Status.choices,
            "staff": _hk_staff(request.tenant),
            "hk_stats": hk_stats,
            "hotel": hotel,
        },
    )


@feature_required("housekeeping")
@role_required(*HOUSEKEEPING)
@require_POST
def hk_set_status(request, room_id):
    room = get_object_or_404(Room, pk=room_id, tenant=request.tenant)
    new_status = request.POST.get("status")
    if new_status not in dict(Room.Status.choices):
        messages.error(request, _("Noto‘g‘ri status."))
    else:
        set_room_status(room, new_status, user=request.user)
        if new_status == Room.Status.DIRTY:
            HousekeepingTask.objects.create(
                tenant=request.tenant,
                room=room,
                title=_("Tozalash"),
            )
        messages.success(
            request,
            _("Xona %(number)s: %(status)s")
            % {"number": room.number, "status": room.get_status_display()},
        )
    return redirect("housekeeping:board")


@feature_required("housekeeping")
@role_required(*HOUSEKEEPING)
@require_POST
def hk_assign_task(request, task_id):
    task = get_object_or_404(HousekeepingTask, pk=task_id, tenant=request.tenant)
    user_id = request.POST.get("assigned_to")
    if not user_id:
        messages.error(request, _("Xodim tanlang."))
        return redirect("housekeeping:board")
    staff = _hk_staff(request.tenant).filter(pk=user_id).first()
    if staff is None:
        messages.error(request, _("Noto‘g‘ri xodim."))
        return redirect("housekeeping:board")
    assign_task(task, staff)
    messages.success(request, _("Biriktirildi: %(user)s") % {"user": staff.get_username()})
    return redirect("housekeeping:board")


@feature_required("housekeeping")
@role_required(*HOUSEKEEPING)
@require_POST
def hk_complete_task(request, task_id):
    task = get_object_or_404(HousekeepingTask, pk=task_id, tenant=request.tenant)
    complete_task(task, user=request.user)
    messages.success(request, _("Vazifa bajarildi."))
    return redirect("housekeeping:board")


@feature_required("maintenance")
@role_required(*HOUSEKEEPING)
@require_POST
def hk_report_maintenance(request, room_id):
    from maintenance.models import MaintenanceTicket
    from maintenance.services import open_ticket

    room = get_object_or_404(Room, pk=room_id, tenant=request.tenant)
    title = (request.POST.get("title") or "").strip() or _("Xona nosozligi")
    description = (request.POST.get("description") or "").strip()
    set_ooo = request.POST.get("set_ooo") == "1"
    ticket = MaintenanceTicket.objects.create(
        tenant=request.tenant,
        room=room,
        title=title,
        description=description,
        set_room_ooo=set_ooo,
        created_by=request.user,
    )
    open_ticket(ticket)
    messages.success(request, _("Ta’mirlash arizasi yaratildi: %(room)s") % {"room": room.number})
    return redirect("housekeeping:board")
