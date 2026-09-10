from django.utils.translation import gettext as _
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from core.mixins import feature_required, role_required
from core.roles import OPS_MANAGER
from core.staff import tenant_staff_users

from .forms import MaintenanceTicketForm
from .models import MaintenanceTicket
from .services import assign_ticket, complete_ticket, open_ticket

User = get_user_model()


def _maintenance_staff(tenant):
    return tenant_staff_users(tenant)


@feature_required("maintenance")
@role_required(*OPS_MANAGER)
def ticket_list(request):
    status = request.GET.get("status", "open")
    tickets = MaintenanceTicket.objects.filter(tenant=request.tenant).select_related(
        "room", "assignee", "created_by"
    )
    hotel = getattr(request, "active_property", None)
    if hotel is not None:
        tickets = tickets.filter(room__property=hotel)
    base = tickets
    open_count = base.filter(status=MaintenanceTicket.Status.OPEN).count()
    in_progress_count = base.filter(status=MaintenanceTicket.Status.IN_PROGRESS).count()
    high_count = base.filter(
        priority=MaintenanceTicket.Priority.HIGH,
        status__in=[
            MaintenanceTicket.Status.OPEN,
            MaintenanceTicket.Status.IN_PROGRESS,
        ],
    ).count()
    if status == "open":
        tickets = tickets.filter(
            status__in=[
                MaintenanceTicket.Status.OPEN,
                MaintenanceTicket.Status.IN_PROGRESS,
            ]
        )
    elif status in {s.value for s in MaintenanceTicket.Status}:
        tickets = tickets.filter(status=status)
    return render(
        request,
        "maintenance/ticket_list.html",
        {
            "tickets": tickets,
            "status": status,
            "statuses": MaintenanceTicket.Status.choices,
            "staff": _maintenance_staff(request.tenant),
            "open_count": open_count,
            "in_progress_count": in_progress_count,
            "high_count": high_count,
        },
    )


@feature_required("maintenance")
@role_required(*OPS_MANAGER)
@require_http_methods(["GET", "POST"])
def ticket_create(request):
    form = MaintenanceTicketForm(request.POST or None, tenant=request.tenant)
    if request.method == "POST" and form.is_valid():
        ticket = form.save(commit=False)
        ticket.tenant = request.tenant
        ticket.created_by = request.user
        ticket.save()
        open_ticket(ticket)
        messages.success(request, _("Ariza ochildi."))
        return redirect("maintenance:list")
    return render(request, "maintenance/ticket_form.html", {"form": form})


@feature_required("maintenance")
@role_required(*OPS_MANAGER)
@require_POST
def ticket_assign(request, pk):
    ticket = get_object_or_404(MaintenanceTicket, pk=pk, tenant=request.tenant)
    user_id = request.POST.get("assignee_id")
    user = get_object_or_404(User, pk=user_id, is_active=True)
    try:
        assign_ticket(ticket, user)
        messages.success(request, _("Ariza biriktirildi."))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("maintenance:list")


@feature_required("maintenance")
@role_required(*OPS_MANAGER)
@require_POST
def ticket_complete(request, pk):
    ticket = get_object_or_404(MaintenanceTicket, pk=pk, tenant=request.tenant)
    try:
        complete_ticket(ticket, user=request.user)
        messages.success(request, _("Ariza yopildi."))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("maintenance:list")
