from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from core.models import log_activity
from finance.models import Expense, ExpenseCategory
from housekeeping.services import set_room_status
from properties.models import Room
from reports.day_lock import assert_day_open

from .models import MaintenanceTicket

CAT_OPERATING = "Ta’mir (joriy)"
CAT_REINVESTMENT = "Reinvestitsiya"


def ensure_maintenance_categories(tenant) -> tuple[ExpenseCategory, ExpenseCategory]:
    op, _ = ExpenseCategory.objects.get_or_create(
        tenant=tenant, name=CAT_OPERATING, defaults={"is_active": True}
    )
    rein, _ = ExpenseCategory.objects.get_or_create(
        tenant=tenant, name=CAT_REINVESTMENT, defaults={"is_active": True}
    )
    return op, rein


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


@transaction.atomic
def cancel_ticket(ticket: MaintenanceTicket, user=None) -> MaintenanceTicket:
    if ticket.status in {
        MaintenanceTicket.Status.DONE,
        MaintenanceTicket.Status.CANCELLED,
    }:
        raise ValidationError(_("Ariza allaqachon yopilgan."))
    ticket.status = MaintenanceTicket.Status.CANCELLED
    ticket.save(update_fields=["status", "updated_at"])
    if ticket.set_room_ooo and ticket.room_id and ticket.room.status == Room.Status.OUT_OF_ORDER:
        set_room_status(
            ticket.room, Room.Status.DIRTY, user=user, note="Maintenance cancelled"
        )
    return ticket


@transaction.atomic
def record_maintenance_spend(
    tenant,
    user,
    *,
    hotel,
    title: str,
    amount: Decimal,
    expense_date,
    funding: str,
    payment_method: str = Expense.PaymentMethod.CASH,
    ticket: MaintenanceTicket | None = None,
    notes: str = "",
    currency: str | None = None,
) -> Expense:
    """
    Remont bo‘limidan to‘lov yozish (darhol PAID).
    funding=operating → Sof; reinvestment → faqat foyda ulushi.
    """
    if hotel is None:
        raise ValidationError(_("Filial tanlang."))
    if amount is None or Decimal(amount) <= 0:
        raise ValidationError(_("Summa 0 dan katta bo‘lishi kerak."))
    if funding not in dict(Expense.Funding.choices):
        raise ValidationError(_("Moliyalashtirish turi noto‘g‘ri."))
    if ticket is not None and ticket.tenant_id != tenant.id:
        raise ValidationError(_("Ariza topilmadi."))

    assert_day_open(
        tenant, expense_date or timezone.localdate(), user, hotel=hotel
    )
    cat_op, cat_re = ensure_maintenance_categories(tenant)
    category = cat_re if funding == Expense.Funding.REINVESTMENT else cat_op

    expense = Expense(
        tenant=tenant,
        hotel=hotel,
        category=category,
        maintenance_ticket=ticket,
        funding=funding,
        title=title.strip(),
        amount=Decimal(amount),
        currency=currency or tenant.currency or "UZS",
        expense_date=expense_date or timezone.localdate(),
        payment_method=payment_method,
        status=Expense.Status.PAID,
        notes=notes or "",
        created_by=user,
        paid_by=user,
        paid_at=timezone.now(),
    )
    expense.save()
    log_activity(
        tenant=tenant,
        user=user,
        action="maintenance_spend",
        model="Expense",
        object_id=expense.pk,
        payload={
            "amount": str(expense.amount),
            "funding": funding,
            "title": expense.title,
            "ticket_id": ticket.pk if ticket else None,
        },
    )
    return expense


@transaction.atomic
def void_maintenance_spend(expense: Expense, user, *, reason: str = "") -> Expense:
    """Xato yozilgan Remont to‘lovini hisobdan chiqarish (PAID → REJECTED)."""
    if expense.status != Expense.Status.PAID:
        raise ValidationError(_("Faqat to‘langan xarajat bekor qilinadi."))
    reason = (reason or "").strip() or _("Remont xarajati bekor qilindi.")
    assert_day_open(
        expense.tenant,
        timezone.localdate(),
        user,
        hotel=expense.hotel,
    )
    expense.status = Expense.Status.REJECTED
    expense.rejected_by = user
    expense.rejected_at = timezone.now()
    expense.rejection_reason = reason
    expense.save(
        update_fields=[
            "status",
            "rejected_by",
            "rejected_at",
            "rejection_reason",
            "updated_at",
        ]
    )
    log_activity(
        tenant=expense.tenant,
        user=user,
        action="maintenance_spend_void",
        model="Expense",
        object_id=expense.pk,
        payload={
            "amount": str(expense.amount),
            "funding": expense.funding,
            "title": expense.title,
            "reason": reason,
        },
    )
    return expense
