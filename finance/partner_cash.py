"""
Ulushdorlar o‘rtasida naqd oqimi nazorati.

Sof foyda / P&L / Foyda ulushi ledgeriga TEKMAYDI.
Faqat: topshirish → tasdiq → saqlash → sarf → qoldiq.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import PartnerCashHandover, PartnerCashSpend, ProfitPartner

ZERO = Decimal("0.00")


def _q(value) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(value).quantize(Decimal("0.01"))


def holder_balance(tenant, holder: ProfitPartner) -> dict:
    """Tasdiqlangan qabul − sarflar = qo‘ldagi qoldiq."""
    received = (
        PartnerCashHandover.objects.filter(
            tenant=tenant,
            to_partner=holder,
            status=PartnerCashHandover.Status.CONFIRMED,
        ).aggregate(s=Sum("confirmed_amount"))["s"]
        or ZERO
    )
    spent = (
        PartnerCashSpend.objects.filter(tenant=tenant, holder=holder).aggregate(
            s=Sum("amount_base")
        )["s"]
        or ZERO
    )
    received = _q(received)
    spent = _q(spent)
    return {
        "holder": holder,
        "received": received,
        "spent": spent,
        "remaining": _q(received - spent),
        "pending_in": _q(
            PartnerCashHandover.objects.filter(
                tenant=tenant,
                to_partner=holder,
                status=PartnerCashHandover.Status.PENDING,
            ).aggregate(s=Sum("amount_base"))["s"]
            or ZERO
        ),
    }


def build_partner_cash_board(tenant) -> dict:
    partners = list(
        ProfitPartner.objects.filter(tenant=tenant, is_active=True).order_by(
            "-share_percent", "name"
        )
    )
    balances = [holder_balance(tenant, p) for p in partners]
    handovers = list(
        PartnerCashHandover.objects.filter(tenant=tenant)
        .select_related("from_partner", "to_partner", "created_by", "confirmed_by")
        .order_by("-handed_on", "-id")[:80]
    )
    spends = list(
        PartnerCashSpend.objects.filter(tenant=tenant)
        .select_related("holder", "created_by")
        .order_by("-spent_on", "-id")[:80]
    )
    pending = [h for h in handovers if h.status == PartnerCashHandover.Status.PENDING]
    total_remaining = _q(sum((b["remaining"] for b in balances), ZERO))
    return {
        "balances": balances,
        "handovers": handovers,
        "spends": spends,
        "pending": pending,
        "total_remaining": total_remaining,
        "partners": partners,
    }


@transaction.atomic
def create_handover(
    tenant,
    user,
    *,
    from_partner: ProfitPartner,
    to_partner: ProfitPartner,
    amount: Decimal,
    handed_on: date | None = None,
    note: str = "",
    currency: str | None = None,
) -> PartnerCashHandover:
    if from_partner.tenant_id != tenant.id or to_partner.tenant_id != tenant.id:
        raise ValidationError(_("Sherik topilmadi."))
    if from_partner.pk == to_partner.pk:
        raise ValidationError(_("Bir xil ulushdorga topshirish mumkin emas."))
    amount = _q(amount)
    if amount <= 0:
        raise ValidationError(_("Summa 0 dan katta bo‘lishi kerak."))
    return PartnerCashHandover.objects.create(
        tenant=tenant,
        from_partner=from_partner,
        to_partner=to_partner,
        amount=amount,
        currency=currency or tenant.currency or "UZS",
        handed_on=handed_on or timezone.localdate(),
        note=(note or "").strip(),
        status=PartnerCashHandover.Status.PENDING,
        created_by=user,
    )


@transaction.atomic
def confirm_handover(
    tenant,
    user,
    handover: PartnerCashHandover,
    *,
    confirmed_amount: Decimal | None = None,
    confirm_note: str = "",
) -> PartnerCashHandover:
    if handover.tenant_id != tenant.id:
        raise ValidationError(_("Topshiriq topilmadi."))
    if handover.status != PartnerCashHandover.Status.PENDING:
        raise ValidationError(_("Faqat kutilayotgan topshiriqni tasdiqlash mumkin."))
    amt = _q(confirmed_amount if confirmed_amount is not None else handover.amount)
    if amt <= 0:
        raise ValidationError(_("Qabul qilingan summa 0 dan katta bo‘lishi kerak."))
    handover.status = PartnerCashHandover.Status.CONFIRMED
    handover.confirmed_amount = amt
    handover.confirmed_at = timezone.now()
    handover.confirmed_by = user
    handover.confirm_note = (confirm_note or "").strip()
    handover.save(
        update_fields=[
            "status",
            "confirmed_amount",
            "confirmed_at",
            "confirmed_by",
            "confirm_note",
        ]
    )
    return handover


@transaction.atomic
def reject_handover(
    tenant,
    user,
    handover: PartnerCashHandover,
    *,
    confirm_note: str = "",
) -> PartnerCashHandover:
    if handover.tenant_id != tenant.id:
        raise ValidationError(_("Topshiriq topilmadi."))
    if handover.status != PartnerCashHandover.Status.PENDING:
        raise ValidationError(_("Faqat kutilayotgan topshiriqni rad etish mumkin."))
    handover.status = PartnerCashHandover.Status.REJECTED
    handover.confirmed_at = timezone.now()
    handover.confirmed_by = user
    handover.confirm_note = (confirm_note or "").strip() or _("Rad etildi")
    handover.save(
        update_fields=["status", "confirmed_at", "confirmed_by", "confirm_note"]
    )
    return handover


@transaction.atomic
def record_cash_spend(
    tenant,
    user,
    *,
    holder: ProfitPartner,
    title: str,
    amount: Decimal,
    spent_on: date | None = None,
    note: str = "",
    currency: str | None = None,
    allow_overdraw: bool = False,
) -> PartnerCashSpend:
    if holder.tenant_id != tenant.id:
        raise ValidationError(_("Sherik topilmadi."))
    title = (title or "").strip()
    if not title:
        raise ValidationError(_("Sarf nomi kerak."))
    amount = _q(amount)
    if amount <= 0:
        raise ValidationError(_("Summa 0 dan katta bo‘lishi kerak."))
    bal = holder_balance(tenant, holder)
    if not allow_overdraw and amount > bal["remaining"]:
        raise ValidationError(
            _(
                "Qoldiq yetarli emas. Qo‘lda: %(r)s. Avval topshiriqni tasdiqlang "
                "yoki summani kamaytiring."
            )
            % {"r": bal["remaining"]}
        )
    return PartnerCashSpend.objects.create(
        tenant=tenant,
        holder=holder,
        title=title,
        amount=amount,
        currency=currency or tenant.currency or "UZS",
        spent_on=spent_on or timezone.localdate(),
        note=(note or "").strip(),
        created_by=user,
    )
