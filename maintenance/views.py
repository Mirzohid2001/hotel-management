from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST

from core.mixins import feature_required, role_required
from core.roles import OPS_MANAGER
from core.staff import tenant_staff_users
from finance.models import Expense

from .forms import MaintenanceSpendForm, MaintenanceTicketForm
from .models import MaintenanceTicket
from .services import (
    CAT_OPERATING,
    CAT_REINVESTMENT,
    assign_ticket,
    cancel_ticket,
    complete_ticket,
    delete_ticket,
    open_ticket,
    record_maintenance_spend,
    update_maintenance_spend,
    void_maintenance_spend,
)
from finance.services import delete_expense

User = get_user_model()


def _maintenance_staff(tenant):
    return tenant_staff_users(tenant)


def _active_hotel(request):
    return getattr(request, "active_property", None)


@feature_required("maintenance")
@role_required(*OPS_MANAGER)
def ticket_list(request):
    tab = request.GET.get("tab", "tickets")
    if tab not in {"tickets", "costs"}:
        tab = "tickets"
    status = request.GET.get("status", "open")
    hotel = _active_hotel(request)

    tickets = MaintenanceTicket.objects.filter(tenant=request.tenant).select_related(
        "room", "assignee", "created_by"
    )
    if hotel is not None:
        tickets = tickets.filter(Q(room__property=hotel) | Q(room__isnull=True))
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

    costs = Expense.objects.filter(tenant=request.tenant).filter(
        Q(funding=Expense.Funding.REINVESTMENT)
        | Q(category__name__in=[CAT_OPERATING, CAT_REINVESTMENT])
        | Q(maintenance_ticket__isnull=False)
    ).select_related("category", "maintenance_ticket", "hotel")
    if hotel is not None:
        costs = costs.filter(hotel=hotel)
    costs = costs.order_by("-expense_date", "-id")
    cost_operating = costs.filter(
        funding=Expense.Funding.OPERATING, status=Expense.Status.PAID
    ).aggregate(s=Sum("amount_base"))["s"] or Decimal("0")
    cost_reinvest = costs.filter(
        funding=Expense.Funding.REINVESTMENT, status=Expense.Status.PAID
    ).aggregate(s=Sum("amount_base"))["s"] or Decimal("0")

    return render(
        request,
        "maintenance/ticket_list.html",
        {
            "tab": tab,
            "tickets": tickets,
            "status": status,
            "statuses": MaintenanceTicket.Status.choices,
            "staff": _maintenance_staff(request.tenant),
            "open_count": open_count,
            "in_progress_count": in_progress_count,
            "high_count": high_count,
            "costs": costs[:200],
            "cost_operating": cost_operating,
            "cost_reinvest": cost_reinvest,
        },
    )


@feature_required("maintenance")
@role_required(*OPS_MANAGER)
@require_http_methods(["GET", "POST"])
def ticket_create(request):
    hotel = _active_hotel(request)
    form = MaintenanceTicketForm(
        request.POST or None, tenant=request.tenant, hotel=hotel
    )
    if request.method == "POST" and form.is_valid():
        ticket = form.save(commit=False)
        ticket.tenant = request.tenant
        ticket.created_by = request.user
        ticket.save()
        open_ticket(ticket)
        messages.success(request, _("Ariza ochildi."))
        return redirect("maintenance:list")
    return render(request, "maintenance/ticket_form.html", {"form": form, "title": _("Yangi ariza")})


@feature_required("maintenance")
@role_required(*OPS_MANAGER)
@require_http_methods(["GET", "POST"])
def ticket_edit(request, pk):
    ticket = get_object_or_404(MaintenanceTicket, pk=pk, tenant=request.tenant)
    if ticket.status in {
        MaintenanceTicket.Status.DONE,
        MaintenanceTicket.Status.CANCELLED,
    }:
        messages.error(request, _("Yopilgan arizani tahrirlab bo‘lmaydi."))
        return redirect("maintenance:list")
    hotel = _active_hotel(request)
    form = MaintenanceTicketForm(
        request.POST or None,
        instance=ticket,
        tenant=request.tenant,
        hotel=hotel,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Ariza yangilandi."))
        return redirect("maintenance:list")
    return render(
        request,
        "maintenance/ticket_form.html",
        {"form": form, "title": _("Arizani tahrirlash"), "ticket": ticket},
    )


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


@feature_required("maintenance")
@role_required(*OPS_MANAGER)
@require_POST
def ticket_cancel(request, pk):
    ticket = get_object_or_404(MaintenanceTicket, pk=pk, tenant=request.tenant)
    try:
        cancel_ticket(ticket, user=request.user)
        messages.success(request, _("Ariza bekor qilindi."))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("maintenance:list")


@feature_required("maintenance")
@role_required(*OPS_MANAGER)
@require_POST
def ticket_delete(request, pk):
    ticket = get_object_or_404(MaintenanceTicket, pk=pk, tenant=request.tenant)
    try:
        delete_ticket(ticket, user=request.user)
        messages.success(request, _("Ariza o‘chirildi."))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("maintenance:list")


@feature_required("maintenance")
@role_required(*OPS_MANAGER)
@require_http_methods(["GET", "POST"])
def spend_create(request):
    hotel = _active_hotel(request)
    if hotel is None:
        messages.error(request, _("Xarajat uchun avval filial tanlang."))
        return redirect("maintenance:list")
    form = MaintenanceSpendForm(
        request.POST or None, tenant=request.tenant, hotel=hotel
    )
    if not request.POST:
        form.fields["expense_date"].initial = timezone.localdate()
    if request.method == "POST" and form.is_valid():
        try:
            record_maintenance_spend(
                request.tenant,
                request.user,
                hotel=hotel,
                title=form.cleaned_data["title"],
                amount=form.cleaned_data["amount"],
                expense_date=form.cleaned_data["expense_date"],
                funding=form.cleaned_data["funding"],
                payment_method=form.cleaned_data["payment_method"],
                ticket=form.cleaned_data.get("ticket"),
                notes=form.cleaned_data.get("notes") or "",
                currency=form.cleaned_data.get("currency"),
            )
            messages.success(request, _("Xarajat yozildi."))
            return redirect(reverse("maintenance:list") + "?tab=costs")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    return render(
        request,
        "maintenance/spend_form.html",
        {"form": form, "hotel": hotel, "title": _("Xarajat yozish")},
    )


@feature_required("maintenance")
@role_required(*OPS_MANAGER)
@require_http_methods(["GET", "POST"])
def spend_edit(request, pk):
    expense = get_object_or_404(Expense, pk=pk, tenant=request.tenant)
    hotel = _active_hotel(request)
    if hotel is not None and expense.hotel_id and expense.hotel_id != hotel.pk:
        messages.error(request, _("Bu xarajat boshqa filialga tegishli."))
        return redirect(reverse("maintenance:list") + "?tab=costs")
    if expense.status != Expense.Status.PAID:
        messages.error(request, _("Faqat to‘langan xarajat tahrirlanadi."))
        return redirect(reverse("maintenance:list") + "?tab=costs")
    form = MaintenanceSpendForm(
        request.POST or None,
        tenant=request.tenant,
        hotel=expense.hotel or hotel,
        initial={
            "title": expense.title,
            "amount": expense.amount,
            "currency": expense.currency,
            "expense_date": expense.expense_date,
            "funding": expense.funding,
            "payment_method": expense.payment_method,
            "ticket": expense.maintenance_ticket_id,
            "notes": expense.notes,
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            update_maintenance_spend(
                expense,
                request.user,
                title=form.cleaned_data["title"],
                amount=form.cleaned_data["amount"],
                expense_date=form.cleaned_data["expense_date"],
                funding=form.cleaned_data["funding"],
                payment_method=form.cleaned_data["payment_method"],
                ticket=form.cleaned_data.get("ticket"),
                notes=form.cleaned_data.get("notes") or "",
                currency=form.cleaned_data.get("currency"),
            )
            messages.success(request, _("Xarajat yangilandi."))
            return redirect(reverse("maintenance:list") + "?tab=costs")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    return render(
        request,
        "maintenance/spend_form.html",
        {
            "form": form,
            "hotel": expense.hotel or hotel,
            "title": _("Xarajatni tahrirlash"),
            "expense": expense,
        },
    )


@feature_required("maintenance")
@role_required(*OPS_MANAGER)
@require_POST
def spend_void(request, pk):
    expense = get_object_or_404(Expense, pk=pk, tenant=request.tenant)
    hotel = _active_hotel(request)
    if hotel is not None and expense.hotel_id and expense.hotel_id != hotel.pk:
        messages.error(request, _("Bu xarajat boshqa filialga tegishli."))
        return redirect(reverse("maintenance:list") + "?tab=costs")
    reason = (request.POST.get("reason") or "").strip()
    try:
        void_maintenance_spend(expense, request.user, reason=reason)
        messages.success(request, _("Xarajat hisobdan chiqarildi."))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect(reverse("maintenance:list") + "?tab=costs")


@feature_required("maintenance")
@role_required(*OPS_MANAGER)
@require_POST
def spend_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk, tenant=request.tenant)
    hotel = _active_hotel(request)
    if hotel is not None and expense.hotel_id and expense.hotel_id != hotel.pk:
        messages.error(request, _("Bu xarajat boshqa filialga tegishli."))
        return redirect(reverse("maintenance:list") + "?tab=costs")
    try:
        delete_expense(expense, request.user)
        messages.success(request, _("Xarajat o‘chirildi."))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect(reverse("maintenance:list") + "?tab=costs")
