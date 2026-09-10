from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from django.db import transaction
from django.utils import timezone

from core.models import log_activity
from reports.day_lock import assert_day_open

from .models import Expense


@transaction.atomic
def approve_expense(expense: Expense, user) -> Expense:
    if expense.status != Expense.Status.DRAFT:
        raise ValidationError(_("Faqat qoralama rasxodlar tasdiqlanadi."))
    assert_day_open(expense.tenant, timezone.localdate(), user, hotel=expense.hotel)
    expense.status = Expense.Status.APPROVED
    expense.approved_by = user
    expense.save(update_fields=["status", "approved_by", "updated_at"])
    log_activity(
        tenant=expense.tenant,
        user=user,
        action="expense_approved",
        model="Expense",
        object_id=expense.pk,
        payload={"amount": str(expense.amount), "title": expense.title},
    )
    return expense


@transaction.atomic
def reject_expense(expense: Expense, user, *, reason: str = "") -> Expense:
    if expense.status not in {Expense.Status.DRAFT, Expense.Status.APPROVED}:
        raise ValidationError(_("Faqat qoralama/tasdiqlangan rasxodlar rad etiladi."))
    assert_day_open(expense.tenant, timezone.localdate(), user, hotel=expense.hotel)
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError(_("Rad etish sababi kerak."))
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
    return expense


@transaction.atomic
def mark_expense_paid(expense: Expense, user) -> Expense:
    if expense.status != Expense.Status.APPROVED:
        raise ValidationError(_("Faqat tasdiqlangan rasxodlar to‘langan deb belgilanadi."))
    assert_day_open(expense.tenant, timezone.localdate(), user, hotel=expense.hotel)
    expense.status = Expense.Status.PAID
    expense.paid_by = user
    expense.paid_at = timezone.now()
    expense.save(update_fields=["status", "paid_by", "paid_at", "updated_at"])
    log_activity(
        tenant=expense.tenant,
        user=user,
        action="expense_paid",
        model="Expense",
        object_id=expense.pk,
        payload={
            "amount": str(expense.amount),
            "method": expense.payment_method,
            "title": expense.title,
        },
    )
    return expense


EDITABLE_STATUSES = {Expense.Status.DRAFT, Expense.Status.APPROVED}
DELETABLE_STATUSES = {Expense.Status.DRAFT, Expense.Status.REJECTED}


def assert_expense_editable(expense: Expense) -> None:
    if expense.status not in EDITABLE_STATUSES:
        raise ValidationError(_("Faqat qoralama yoki tasdiqlangan (to‘lanmagan) rasxod tahrirlanadi."))


@transaction.atomic
def reopen_expense(expense: Expense, user) -> Expense:
    """Rad etilgan rasxodni qoralamaga qaytarish — qayta tahrirlash/tasdiqlash uchun."""
    if expense.status != Expense.Status.REJECTED:
        raise ValidationError(_("Faqat rad etilgan rasxodlar qayta ochiladi."))
    assert_day_open(expense.tenant, timezone.localdate(), user, hotel=expense.hotel)
    expense.status = Expense.Status.DRAFT
    expense.rejected_by = None
    expense.rejected_at = None
    expense.rejection_reason = ""
    expense.approved_by = None
    expense.save(
        update_fields=[
            "status",
            "rejected_by",
            "rejected_at",
            "rejection_reason",
            "approved_by",
            "updated_at",
        ]
    )
    log_activity(
        tenant=expense.tenant,
        user=user,
        action="expense_reopened",
        model="Expense",
        object_id=expense.pk,
        payload={"title": expense.title, "amount": str(expense.amount)},
    )
    return expense


@transaction.atomic
def delete_expense(expense: Expense, user) -> None:
    if expense.status not in DELETABLE_STATUSES:
        raise ValidationError(_("Faqat qoralama yoki rad etilgan rasxod o‘chiriladi."))
    assert_day_open(expense.tenant, timezone.localdate(), user, hotel=expense.hotel)
    pk = expense.pk
    title = expense.title
    amount = str(expense.amount)
    tenant = expense.tenant
    expense.delete()
    log_activity(
        tenant=tenant,
        user=user,
        action="expense_deleted",
        model="Expense",
        object_id=pk,
        payload={"title": title, "amount": amount},
    )
