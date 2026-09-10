from decimal import Decimal
import json

from django.contrib import messages
from django.db.models import Prefetch
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST

from bookings.models import Reservation
from core.htmx import modal_close_response
from core.mixins import feature_required, role_required, tenant_login_required
from core.roles import CASH, FINANCE, FRONT_DESK_MONEY, MONEY_VOID

from .city_ledger import (
    add_company_payment,
    ar_aging,
    transfer_charges_to_company,
    transfer_open_charges_to_company,
)
from .forms import (
    CashMovementForm,
    ChargeForm,
    CityLedgerTransferForm,
    CloseShiftForm,
    CompanyPaymentForm,
    OpenShiftForm,
    PaymentForm,
    RefundForm,
    SplitPaymentForm,
    StayMinibarForm,
    StayServiceForm,
    VoidForm,
)
from .models import CashShift, CompanyInvoice, CompanyPayment, Folio, FolioCharge, GuestPayment
from .services import (
    add_cash_movement,
    add_charge,
    add_payment,
    add_split_payments,
    close_cash_shift,
    close_folio,
    ensure_folio_for_reservation,
    get_open_shift,
    open_cash_shift,
    open_folio_for_deposit,
    collect_emehmon_fee,
    refund_overpayment,
    void_charge,
    void_payment,
)
from .shift_report import build_shift_report

from reports.chart_data import cash_shift_charts


def _folio_context(folio, reservation, tenant=None):
    t = tenant or reservation.tenant
    billing_company = reservation.company or (
        reservation.guest.company if reservation.guest_id else None
    )
    credit = folio.credit_amount
    charges = list(folio.charges.all())
    payments = list(folio.payments.all())
    return {
        "folio": folio,
        "reservation": reservation,
        "active_charges": [c for c in charges if not c.is_void],
        "voided_charges": [c for c in charges if c.is_void],
        "active_payments": [p for p in payments if not p.is_void],
        "charge_form": ChargeForm(initial={"currency": t.currency or "UZS"}),
        "payment_form": PaymentForm(tenant=t),
        "refund_form": RefundForm(tenant=t, max_amount=credit if credit > 0 else None),
        "service_form": StayServiceForm(tenant=t),
        "minibar_form": StayMinibarForm(tenant=t, hotel=reservation.hotel),
        "city_ledger_form": CityLedgerTransferForm(folio=folio),
        "billing_company": billing_company,
        "can_city_ledger": t.has_feature("company_group") and billing_company is not None,
        "split_form": SplitPaymentForm(),
        "payment_method_choices": GuestPayment.Method.choices,
        "payment_kind_choices": [
            (GuestPayment.Kind.PAYMENT, _("To‘lov")),
            (GuestPayment.Kind.DEPOSIT, _("Depozit")),
        ],
        "can_post_service": t.has_feature("services"),
        "can_post_minibar": t.has_feature("inventory"),
    }


@role_required(*FRONT_DESK_MONEY)
def folio_detail(request, reservation_id):
    reservation = get_object_or_404(Reservation, pk=reservation_id, tenant=request.tenant)
    try:
        if reservation.status in {
            Reservation.Status.CONFIRMED,
            Reservation.Status.INQUIRY,
            Reservation.Status.CHECKED_IN,
        }:
            folio = ensure_folio_for_reservation(reservation, allow_pre_checkin=True)
        else:
            folio = ensure_folio_for_reservation(reservation, allow_pre_checkin=True)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("bookings:detail", pk=reservation_id)
    return render(request, "folio/folio_detail.html", _folio_context(folio, reservation, request.tenant))


@role_required(*FRONT_DESK_MONEY)
@require_http_methods(["POST"])
def folio_add_charge(request, pk):
    folio = get_object_or_404(Folio, pk=pk, tenant=request.tenant)
    form = ChargeForm(request.POST)
    if form.is_valid():
        try:
            add_charge(folio, request.user, **form.cleaned_data)
            messages.success(request, _("Hisob yozuvi qo‘shildi."))
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    else:
        messages.error(request, _("Hisob yozuvi formasi noto‘g‘ri."))
    return redirect("folio:detail", reservation_id=folio.reservation_id)


def _modal_close_response(*, refresh_board: bool = False) -> HttpResponse:
    return modal_close_response(refresh_board=refresh_board)


@role_required(*FRONT_DESK_MONEY)
@require_http_methods(["GET"])
def folio_payment_modal(request, reservation_id):
    reservation = get_object_or_404(Reservation, pk=reservation_id, tenant=request.tenant)
    try:
        folio = ensure_folio_for_reservation(reservation, allow_pre_checkin=True)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("bookings:detail", pk=reservation_id)
    kind = request.GET.get("kind", GuestPayment.Kind.PAYMENT)
    if kind not in {GuestPayment.Kind.PAYMENT, GuestPayment.Kind.DEPOSIT}:
        kind = GuestPayment.Kind.PAYMENT
    initial_amount = folio.balance if folio.balance > 0 else Decimal("0")
    form = PaymentForm(
        tenant=request.tenant,
        initial={
            "kind": kind,
            "amount": initial_amount if initial_amount > 0 else Decimal("1"),
            "method": GuestPayment.Method.CASH,
            "currency": request.tenant.currency or "UZS",
        },
    )
    from_board = request.GET.get("from") == "board"
    title = _("Depozit") if kind == GuestPayment.Kind.DEPOSIT else _("To‘lov")
    return render(
        request,
        "folio/partials/payment_modal.html",
        {
            "folio": folio,
            "reservation": reservation,
            "form": form,
            "title": title,
            "from_board": from_board,
        },
    )


@role_required(*FRONT_DESK_MONEY)
@require_http_methods(["POST"])
def folio_add_payment(request, pk):
    folio = get_object_or_404(Folio, pk=pk, tenant=request.tenant)
    form = PaymentForm(request.POST, tenant=request.tenant)
    from_modal = request.POST.get("from_modal") == "1"
    if form.is_valid():
        try:
            add_payment(folio, request.user, **form.cleaned_data)
            messages.success(request, _("To‘lov qabul qilindi."))
            if request.htmx and from_modal:
                return _modal_close_response(refresh_board=True)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            if request.htmx and from_modal:
                return render(
                    request,
                    "folio/partials/payment_modal.html",
                    {
                        "folio": folio,
                        "reservation": folio.reservation,
                        "form": form,
                        "title": _("To‘lov"),
                        "from_board": request.POST.get("from_board") == "1",
                        "errors": exc.messages,
                    },
                )
    else:
        messages.error(request, _("To‘lov formasi noto‘g‘ri."))
        if request.htmx and from_modal:
            return render(
                request,
                "folio/partials/payment_modal.html",
                {
                    "folio": folio,
                    "reservation": folio.reservation,
                    "form": form,
                    "title": _("To‘lov"),
                    "from_board": request.POST.get("from_board") == "1",
                },
            )
    if request.htmx:
        folio.refresh_from_db()
        return render(
            request,
            "folio/partials/folio_body.html",
            _folio_context(folio, folio.reservation, request.tenant),
        )
    return redirect("folio:detail", reservation_id=folio.reservation_id)


@role_required(*FRONT_DESK_MONEY)
@require_http_methods(["POST"])
def folio_refund(request, pk):
    """Ortib qolgan to‘lovni (sdachi) mehmonga qaytarish."""
    folio = get_object_or_404(Folio, pk=pk, tenant=request.tenant)
    form = RefundForm(
        request.POST,
        tenant=request.tenant,
        max_amount=folio.credit_amount if folio.credit_amount > 0 else None,
    )
    if form.is_valid():
        try:
            refund_overpayment(folio, request.user, **form.cleaned_data)
            messages.success(request, _("Sdachi qaytarildi — ortiqcha to‘lov yozildi."))
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    else:
        messages.error(request, _("Qaytarish formasi noto‘g‘ri."))
    if request.htmx:
        folio.refresh_from_db()
        return render(
            request,
            "folio/partials/folio_body.html",
            _folio_context(folio, folio.reservation, request.tenant),
        )
    return redirect("folio:detail", reservation_id=folio.reservation_id)


@role_required(*FRONT_DESK_MONEY)
@require_http_methods(["POST"])
def folio_add_split(request, pk):
    folio = get_object_or_404(Folio, pk=pk, tenant=request.tenant)
    form = SplitPaymentForm(request.POST)
    if form.is_valid():
        try:
            add_split_payments(folio, request.user, form.lines())
            messages.success(request, _("Bo‘lingan to‘lov qabul qilindi."))
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    else:
        messages.error(request, _("Bo‘lingan to‘lov formasi noto‘g‘ri."))
    if request.htmx:
        folio.refresh_from_db()
        return render(
            request,
            "folio/partials/folio_body.html",
            _folio_context(folio, folio.reservation, request.tenant),
        )
    return redirect("folio:detail", reservation_id=folio.reservation_id)


@role_required(*MONEY_VOID)
@require_POST
def folio_void_charge(request, pk):
    charge = get_object_or_404(FolioCharge, pk=pk, tenant=request.tenant)
    form = VoidForm(request.POST)
    if form.is_valid():
        try:
            void_charge(charge, request.user, reason=form.cleaned_data["reason"])
            messages.success(request, _("Hisob yozuvi bekor qilindi."))
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    else:
        messages.error(request, _("Bekor qilish sababi kerak."))
    return redirect("folio:detail", reservation_id=charge.folio.reservation_id)


@role_required(*MONEY_VOID)
@require_POST
def folio_void_payment(request, pk):
    payment = get_object_or_404(GuestPayment, pk=pk, tenant=request.tenant)
    form = VoidForm(request.POST)
    if form.is_valid():
        try:
            void_payment(payment, request.user, reason=form.cleaned_data["reason"])
            messages.success(request, _("To‘lov bekor qilindi."))
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    else:
        messages.error(request, _("Bekor qilish sababi kerak."))
    return redirect("folio:detail", reservation_id=payment.folio.reservation_id)


@role_required(*FRONT_DESK_MONEY)
@feature_required("services")
@require_POST
def folio_post_service(request, pk):
    folio = get_object_or_404(Folio, pk=pk, tenant=request.tenant)
    form = StayServiceForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        try:
            from services.services import order_service

            order_service(
                reservation=folio.reservation,
                service=form.cleaned_data["service"],
                user=request.user,
                quantity=form.cleaned_data["quantity"],
                note=form.cleaned_data.get("note") or "",
            )
            messages.success(request, _("Xizmat mehmon hisobiga yozildi."))
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    else:
        messages.error(request, _("Xizmat formasi noto‘g‘ri."))
    return redirect("folio:detail", reservation_id=folio.reservation_id)


@role_required(*FRONT_DESK_MONEY)
@feature_required("inventory")
@require_POST
def folio_post_minibar(request, pk):
    folio = get_object_or_404(Folio, pk=pk, tenant=request.tenant)
    form = StayMinibarForm(
        request.POST, tenant=request.tenant, hotel=folio.reservation.hotel
    )
    if form.is_valid():
        try:
            from inventory.services import sell_minibar

            sell_minibar(
                reservation=folio.reservation,
                item=form.cleaned_data["item"],
                user=request.user,
                quantity=form.cleaned_data["quantity"],
            )
            messages.success(request, _("Minibar mehmon hisobiga yozildi."))
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    else:
        messages.error(request, _("Minibar formasi noto‘g‘ri."))
    return redirect("folio:detail", reservation_id=folio.reservation_id)


@role_required(*FRONT_DESK_MONEY)
@require_POST
def folio_deposit(request, reservation_id):
    reservation = get_object_or_404(Reservation, pk=reservation_id, tenant=request.tenant)
    form = PaymentForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        try:
            folio = open_folio_for_deposit(reservation, request.user)
            data = form.cleaned_data
            data["kind"] = GuestPayment.Kind.DEPOSIT
            add_payment(folio, request.user, **data)
            messages.success(request, _("Depozit qabul qilindi."))
            return redirect("folio:detail", reservation_id=reservation.pk)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    else:
        messages.error(request, _("Depozit formasi noto‘g‘ri."))
    return redirect("bookings:detail", pk=reservation_id)


@role_required(*FRONT_DESK_MONEY)
@require_POST
def folio_emehmon(request, reservation_id):
    reservation = get_object_or_404(Reservation, pk=reservation_id, tenant=request.tenant)
    form = PaymentForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        try:
            collect_emehmon_fee(
                reservation,
                request.user,
                amount=form.cleaned_data["amount"],
                method=form.cleaned_data["method"],
                note=form.cleaned_data.get("note") or "",
                currency=form.cleaned_data.get("currency"),
            )
            messages.success(request, _("E-mehmon to‘lovi qabul qilindi."))
            return redirect("folio:detail", reservation_id=reservation.pk)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    else:
        messages.error(request, _("E-mehmon formasi noto‘g‘ri."))
    return redirect("bookings:detail", pk=reservation_id)


@role_required(*CASH)
@require_POST
def folio_close(request, pk):
    folio = get_object_or_404(Folio, pk=pk, tenant=request.tenant)
    try:
        close_folio(folio)
        messages.success(request, _("Mehmon hisobi yopildi."))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("folio:detail", reservation_id=folio.reservation_id)


@role_required(*FRONT_DESK_MONEY)
def folio_receipt(request, pk):
    from .models import FolioCharge, GuestPayment

    folio = get_object_or_404(
        Folio.objects.select_related(
            "tenant",
            "reservation",
            "reservation__guest",
            "reservation__hotel",
            "reservation__room",
        ).prefetch_related(
            Prefetch(
                "charges",
                queryset=FolioCharge.objects.filter(is_void=False).order_by("created_at"),
            ),
            Prefetch(
                "payments",
                queryset=GuestPayment.objects.filter(is_void=False).order_by("created_at"),
            ),
        ),
        pk=pk,
        tenant=request.tenant,
    )
    return render(
        request,
        "folio/receipt.html",
        {"folio": folio, "tenant": request.tenant},
    )


@feature_required("cash_shift")
@role_required(*CASH)
def cash_shift_page(request):
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        messages.error(request, _("Kassa uchun avval filial tanlang."))
        return redirect("properties:list")
    open_shift = get_open_shift(request.tenant, hotel=hotel)
    history = CashShift.objects.filter(tenant=request.tenant, hotel=hotel).select_related(
        "opened_by", "closed_by", "hotel"
    )[:20]
    report = build_shift_report(open_shift) if open_shift else None
    expected = report["expected_cash"] if report else Decimal("0")
    history_chart = [
        {
            "label": s.opened_at.strftime("%d.%m"),
            "variance": s.variance,
        }
        for s in reversed(list(history))
        if s.closed_at and s.variance is not None
    ][:10]
    chart_data = cash_shift_charts(report, history_chart, currency=request.tenant.currency)
    return render(
        request,
        "folio/cash_shift.html",
        {
            "open_shift": open_shift,
            "report": report,
            "expected_cash": expected,
            "history": history,
            "hotel": hotel,
            "open_form": OpenShiftForm(),
            "close_form": CloseShiftForm(
                initial={"closing_cash": expected} if open_shift else None
            ),
            "movement_form": CashMovementForm(tenant=request.tenant),
            "chart_data": chart_data,
        },
    )


@feature_required("cash_shift")
@role_required(*CASH)
def cash_shift_detail(request, pk):
    shift = get_object_or_404(CashShift, pk=pk, tenant=request.tenant)
    hotel = getattr(request, "active_property", None)
    if hotel is not None and shift.hotel_id and shift.hotel_id != hotel.pk:
        messages.error(request, _("Bu smena boshqa filialga tegishli."))
        return redirect("folio:cash_shift")
    report = build_shift_report(shift)
    return render(
        request,
        "folio/cash_shift_detail.html",
        {"shift": shift, "report": report},
    )


@feature_required("cash_shift")
@role_required(*CASH)
def cash_shift_print(request, pk):
    shift = get_object_or_404(CashShift, pk=pk, tenant=request.tenant)
    hotel = getattr(request, "active_property", None)
    if hotel is not None and shift.hotel_id and shift.hotel_id != hotel.pk:
        messages.error(request, _("Bu smena boshqa filialga tegishli."))
        return redirect("folio:cash_shift")
    report = build_shift_report(shift)
    return render(
        request,
        "folio/cash_shift_print.html",
        {"shift": shift, "report": report, "tenant": request.tenant},
    )


@feature_required("cash_shift")
@role_required(*CASH)
@require_POST
def cash_shift_open(request):
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        messages.error(request, _("Kassa uchun avval filial tanlang."))
        return redirect("folio:cash_shift")
    form = OpenShiftForm(request.POST)
    if form.is_valid():
        try:
            open_cash_shift(
                request.tenant,
                request.user,
                form.cleaned_data["opening_float"],
                hotel=hotel,
            )
            messages.success(request, _("Kassa smena ochildi."))
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    else:
        messages.error(request, _("Forma noto‘g‘ri."))
    return redirect("folio:cash_shift")


@feature_required("cash_shift")
@role_required(*CASH)
@require_POST
def cash_shift_close(request):
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        messages.error(request, _("Kassa uchun avval filial tanlang."))
        return redirect("folio:cash_shift")
    shift = get_open_shift(request.tenant, hotel=hotel)
    if not shift:
        messages.error(request, _("Ochiq smena yo‘q."))
        return redirect("folio:cash_shift")
    form = CloseShiftForm(request.POST)
    if form.is_valid():
        try:
            closed = close_cash_shift(
                shift,
                request.user,
                form.cleaned_data["closing_cash"],
                notes=form.cleaned_data.get("notes") or "",
            )
            messages.success(
                request,
                _("Smena yopildi. Farq: %(v)s") % {"v": closed.variance},
            )
            return redirect("folio:cash_shift_detail", pk=closed.pk)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    else:
        messages.error(request, _("Forma noto‘g‘ri."))
    return redirect("folio:cash_shift")


@feature_required("cash_shift")
@role_required(*CASH)
@require_POST
def cash_shift_movement(request):
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        messages.error(request, _("Kassa uchun avval filial tanlang."))
        return redirect("folio:cash_shift")
    shift = get_open_shift(request.tenant, hotel=hotel)
    if shift is None:
        messages.error(request, _("Ochiq smena yo‘q."))
        return redirect("folio:cash_shift")
    form = CashMovementForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        try:
            add_cash_movement(
                shift,
                request.user,
                kind=form.cleaned_data["kind"],
                amount=form.cleaned_data["amount"],
                note=form.cleaned_data.get("note") or "",
                currency=form.cleaned_data.get("currency"),
            )
            messages.success(request, _("Kassa harakati yozildi."))
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    else:
        messages.error(request, _("Forma noto‘g‘ri."))
    return redirect("folio:cash_shift")


@role_required(*FRONT_DESK_MONEY)
def folio_pdf(request, pk):
    from .models import FolioCharge, GuestPayment

    folio = get_object_or_404(
        Folio.objects.select_related(
            "tenant",
            "reservation",
            "reservation__guest",
            "reservation__hotel",
            "reservation__room",
        ).prefetch_related(
            Prefetch(
                "charges",
                queryset=FolioCharge.objects.filter(is_void=False).order_by("created_at"),
            ),
            Prefetch(
                "payments",
                queryset=GuestPayment.objects.filter(is_void=False).order_by("created_at"),
            ),
        ),
        pk=pk,
        tenant=request.tenant,
    )
    from .pdf import build_folio_pdf

    pdf = build_folio_pdf(folio)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="invoice-{folio.reservation.code}.pdf"'
    return response


@feature_required("company_group")
@role_required(*FINANCE)
@require_POST
def folio_to_city_ledger(request, pk):
    folio = get_object_or_404(
        Folio.objects.select_related("reservation", "reservation__guest", "reservation__company"),
        pk=pk,
        tenant=request.tenant,
    )
    form = CityLedgerTransferForm(request.POST, folio=folio)
    if not form.is_valid():
        messages.error(request, _("Kompaniya hisobi formasi noto‘g‘ri."))
        return redirect("folio:detail", reservation_id=folio.reservation_id)
    try:
        if form.cleaned_data.get("transfer_all"):
            invoice = transfer_open_charges_to_company(
                folio, request.user, notes=form.cleaned_data.get("notes") or ""
            )
        else:
            invoice = transfer_charges_to_company(
                folio,
                request.user,
                form.cleaned_data["charge_ids"],
                notes=form.cleaned_data.get("notes") or "",
            )
        messages.success(
            request,
            _("Kompaniya hisobi: %(code)s · %(bal)s")
            % {"code": invoice.code, "bal": invoice.balance},
        )
        return redirect("folio:invoice_detail", pk=invoice.pk)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("folio:detail", reservation_id=folio.reservation_id)


@feature_required("company_group")
@role_required(*FINANCE)
def city_ledger_list(request):
    aging = ar_aging(request.tenant)
    open_invoices = (
        CompanyInvoice.objects.filter(
            tenant=request.tenant,
            status__in=[CompanyInvoice.Status.OPEN, CompanyInvoice.Status.PARTIAL],
        )
        .select_related("company", "hotel")
        .order_by("due_date", "issued_at")[:100]
    )
    return render(
        request,
        "folio/city_ledger_list.html",
        {"aging": aging, "open_invoices": open_invoices},
    )


@feature_required("company_group")
@role_required(*FINANCE)
def invoice_detail(request, pk):
    invoice = get_object_or_404(
        CompanyInvoice.objects.select_related("company", "hotel", "source_folio").prefetch_related(
            "lines__source_reservation",
            Prefetch(
                "payments",
                queryset=CompanyPayment.objects.filter(is_void=False).order_by("created_at"),
            ),
        ),
        pk=pk,
        tenant=request.tenant,
    )
    return render(
        request,
        "folio/invoice_detail.html",
        {
            "invoice": invoice,
            "payment_form": CompanyPaymentForm(
                tenant=request.tenant,
                initial={
                    "amount": invoice.balance if invoice.balance > 0 else Decimal("0"),
                    "method": GuestPayment.Method.TRANSFER,
                },
            ),
        },
    )


@feature_required("company_group")
@role_required(*FINANCE)
def invoice_pdf(request, pk):
    invoice = get_object_or_404(
        CompanyInvoice.objects.select_related(
            "tenant", "company", "hotel"
        ).prefetch_related(
            "lines__source_reservation",
            Prefetch(
                "payments",
                queryset=CompanyPayment.objects.filter(is_void=False).order_by("created_at"),
            ),
        ),
        pk=pk,
        tenant=request.tenant,
    )
    from .pdf import build_company_invoice_pdf

    pdf = build_company_invoice_pdf(invoice)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="invoice-{invoice.code}.pdf"'
    return response


@feature_required("company_group")
@role_required(*FINANCE)
@require_POST
def invoice_add_payment(request, pk):
    invoice = get_object_or_404(CompanyInvoice, pk=pk, tenant=request.tenant)
    form = CompanyPaymentForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        try:
            add_company_payment(invoice, request.user, **form.cleaned_data)
            messages.success(request, _("Kompaniya to‘lovi qabul qilindi."))
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    else:
        messages.error(request, _("To‘lov formasi noto‘g‘ri."))
    return redirect("folio:invoice_detail", pk=pk)
