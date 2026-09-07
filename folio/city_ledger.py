from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from django.db import transaction
from django.utils import timezone

from .models import (
    CompanyInvoice,
    CompanyInvoiceLine,
    CompanyPayment,
    Folio,
    FolioCharge,
    GuestPayment,
)
from .services import void_charge


def generate_invoice_code(tenant, on_date=None) -> str:
    day = on_date or timezone.localdate()
    prefix = f"INV-{day.year}-"
    last = (
        CompanyInvoice.objects.filter(tenant=tenant, code__startswith=prefix)
        .order_by("-code")
        .values_list("code", flat=True)
        .first()
    )
    if last:
        try:
            n = int(last.split("-")[-1]) + 1
        except ValueError:
            n = 1
    else:
        n = 1
    return f"{prefix}{n:04d}"


def resolve_billing_company(folio: Folio, company=None):
    if company is not None:
        return company
    reservation = folio.reservation
    return reservation.company or (reservation.guest.company if reservation.guest_id else None)


def company_open_balance(company) -> Decimal:
    total = Decimal("0")
    for inv in CompanyInvoice.objects.filter(
        company=company,
        status__in=[
            CompanyInvoice.Status.OPEN,
            CompanyInvoice.Status.PARTIAL,
        ],
    ):
        total += inv.balance
    return total


@transaction.atomic
def transfer_charges_to_company(
    folio: Folio,
    user,
    charge_ids: list[int],
    *,
    company=None,
    notes: str = "",
) -> CompanyInvoice:
    if not folio.is_open:
        raise ValidationError(_("Mehmon hisobi yopilgan."))
    company = resolve_billing_company(folio, company)
    if company is None:
        raise ValidationError(_("Avval bron (yoki mehmon) ga kompaniya biriktiring."))
    if company.tenant_id != folio.tenant_id:
        raise ValidationError(_("Kompaniya shu mehmonxonaga tegishli bo‘lishi kerak."))

    charges = list(
        FolioCharge.objects.filter(
            folio=folio,
            pk__in=charge_ids,
            is_void=False,
        ).select_for_update()
    )
    if not charges:
        raise ValidationError(_("O‘tkazish uchun kamida bitta faol yozuv tanlang."))
    if len(charges) != len(set(charge_ids)):
        raise ValidationError(_("Ba’zi yozuvlar yo‘q yoki bekor qilingan."))

    subtotal = sum((c.amount_base or c.amount for c in charges), Decimal("0"))
    tax_percent = folio.tax_percent
    tax = Decimal("0")
    if tax_percent > 0:
        tax = (subtotal * tax_percent / Decimal("100")).quantize(Decimal("0.01"))

    if company.credit_limit > 0:
        projected = company_open_balance(company) + subtotal + tax
        if projected > company.credit_limit:
            raise ValidationError(
                _("Kompaniya kredit limiti %(lim)s oshib ketdi (bo‘lardi %(p)s).")
                % {"lim": company.credit_limit, "p": projected}
            )

    terms = company.payment_terms_days or 30
    due = timezone.localdate() + timedelta(days=terms)
    invoice = CompanyInvoice.objects.create(
        tenant=folio.tenant,
        company=company,
        hotel=folio.reservation.hotel,
        code=generate_invoice_code(folio.tenant),
        due_date=due,
        notes=notes or f"From folio {folio.reservation.code}",
        source_folio=folio,
        created_by=user,
    )

    reservation = folio.reservation
    for charge in charges:
        line = CompanyInvoiceLine(
            tenant=folio.tenant,
            invoice=invoice,
            description=f"{charge.get_charge_type_display()}: {charge.description}",
            amount=charge.amount,
            currency=getattr(charge, "currency", None) or folio.tenant.currency or "UZS",
            source_charge=charge,
            source_reservation=reservation,
        )
        line.fx_rate = getattr(charge, "fx_rate", None) or 1
        line.amount_base = getattr(charge, "amount_base", None) or charge.amount
        line._lock_fx = True
        line.save()
        void_charge(
            charge,
            user,
            reason=f"Transferred to city ledger {invoice.code}",
        )

    if tax > 0:
        CompanyInvoiceLine.objects.create(
            tenant=folio.tenant,
            invoice=invoice,
            description=f"VAT {tax_percent}%",
            amount=tax,
            currency=folio.tenant.currency or "UZS",
            source_reservation=reservation,
        )

    invoice.refresh_status()
    return invoice


@transaction.atomic
def transfer_open_charges_to_company(folio: Folio, user, *, company=None, notes: str = ""):
    ids = list(
        folio.charges.filter(is_void=False).values_list("pk", flat=True)
    )
    return transfer_charges_to_company(folio, user, ids, company=company, notes=notes)


@transaction.atomic
def add_company_payment(
    invoice: CompanyInvoice, user, *, amount, method, note="", currency=None, fx_rate=None
) -> CompanyPayment:
    if invoice.status == CompanyInvoice.Status.VOID:
        raise ValidationError(_("Hisob-faktura bekor qilingan."))
    if amount <= 0:
        raise ValidationError(_("To‘lov summasi musbat bo‘lishi kerak."))
    # Compare in base currency
    pay = CompanyPayment(
        tenant=invoice.tenant,
        invoice=invoice,
        amount=amount,
        method=method or GuestPayment.Method.TRANSFER,
        note=note or "",
        received_by=user,
        currency=currency or invoice.tenant.currency or "UZS",
    )
    if fx_rate is not None:
        pay.fx_rate = fx_rate
        pay._lock_fx = True
    # Preview amount_base before save for limit check
    from core.currency import to_base_amount

    _c, _r, amount_base = to_base_amount(
        invoice.tenant, amount, pay.currency, fx_rate=fx_rate
    )
    if amount_base > invoice.balance:
        raise ValidationError(
            _("Summa hisob-faktura qoldig‘idan oshib ketdi: %(b)s.") % {"b": invoice.balance}
        )
    pay.save()
    invoice.refresh_status()
    return pay


@transaction.atomic
def void_company_payment(payment: CompanyPayment, user, *, reason: str) -> CompanyPayment:
    if payment.is_void:
        raise ValidationError(_("To‘lov allaqachon bekor qilingan."))
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError(_("Bekor qilish sababi kerak."))
    payment.is_void = True
    payment.void_reason = reason
    payment.voided_at = timezone.now()
    payment.voided_by = user
    payment.save(
        update_fields=["is_void", "void_reason", "voided_at", "voided_by", "updated_at"]
    )
    payment.invoice.refresh_status()
    return payment


def ar_aging(tenant) -> dict:
    """Bucket open/partial invoices by days past issue date."""
    today = timezone.localdate()
    buckets = {
        "current": {"label": "0–30", "total": Decimal("0"), "invoices": []},
        "b31_60": {"label": "31–60", "total": Decimal("0"), "invoices": []},
        "b61_90": {"label": "61–90", "total": Decimal("0"), "invoices": []},
        "b90_plus": {"label": "90+", "total": Decimal("0"), "invoices": []},
    }
    qs = (
        CompanyInvoice.objects.filter(
            tenant=tenant,
            status__in=[CompanyInvoice.Status.OPEN, CompanyInvoice.Status.PARTIAL],
        )
        .select_related("company", "hotel")
        .order_by("issued_at")
    )
    for inv in qs:
        bal = inv.balance
        if bal <= 0:
            continue
        age = (today - inv.issued_at.date()).days
        if age <= 30:
            key = "current"
        elif age <= 60:
            key = "b31_60"
        elif age <= 90:
            key = "b61_90"
        else:
            key = "b90_plus"
        buckets[key]["total"] += bal
        buckets[key]["invoices"].append(inv)
    grand = sum((b["total"] for b in buckets.values()), Decimal("0"))
    return {"buckets": buckets, "grand_total": grand}
