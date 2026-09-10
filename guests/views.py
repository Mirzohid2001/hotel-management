from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from bookings.models import Reservation
from core.htmx import oob_select_response, wants_htmx_partial
from core.mixins import role_required, tenant_login_required
from core.roles import FRONT_OFFICE
from folio.city_ledger import company_open_balance
from folio.models import CompanyInvoice

from .forms import (
    CompanyForm,
    CompanyQuickForm,
    GuestDocumentForm,
    GuestForm,
    GuestNoteForm,
    GuestQuickForm,
)
from .models import Company, Guest, GuestDocument


@role_required(*FRONT_OFFICE)
@tenant_login_required
def guest_list(request):
    q = request.GET.get("q", "").strip()
    guests = Guest.objects.filter(tenant=request.tenant)
    if q:
        guests = guests.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(phone__icontains=q)
            | Q(email__icontains=q)
        )
    template = (
        "guests/partials/guest_results.html"
        if wants_htmx_partial(request, target="guest-results")
        else "guests/guest_list.html"
    )
    return render(request, template, {"guests": guests[:100], "q": q})


@role_required(*FRONT_OFFICE)
@tenant_login_required
@require_http_methods(["GET", "POST"])
def guest_create(request):
    form = GuestForm(request.POST or None, tenant=request.tenant)
    if request.method == "POST" and form.is_valid():
        guest = form.save(commit=False)
        guest.tenant = request.tenant
        guest.save()
        messages.success(request, _("Mehmon qo‘shildi."))
        return redirect("guests:detail", pk=guest.pk)
    return render(
        request, "guests/guest_form.html", {"form": form, "title": _("Yangi mehmon")}
    )


@role_required(*FRONT_OFFICE)
@tenant_login_required
@require_http_methods(["GET", "POST"])
def guest_quick_create(request):
    """Inline HTMX create used from reservation/group forms."""
    select_id = request.GET.get("select_id") or request.POST.get("select_id") or "id_guest"
    field_name = request.GET.get("field_name") or request.POST.get("field_name") or "guest"
    form = GuestQuickForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        guest = Guest.objects.create(
            tenant=request.tenant,
            first_name=form.cleaned_data["first_name"],
            last_name=form.cleaned_data.get("last_name") or "",
            phone=form.cleaned_data.get("phone") or "",
            nationality=(form.cleaned_data.get("nationality") or "").strip(),
        )
        GuestDocument.objects.create(
            tenant=request.tenant,
            guest=guest,
            doc_type=form.cleaned_data["doc_type"],
            number=form.cleaned_data["doc_number"],
            issued_country=(form.cleaned_data.get("issued_country") or "").strip(),
        )
        qs = Guest.objects.filter(tenant=request.tenant).order_by("first_name", "last_name")
        return oob_select_response(select_id, field_name, qs, guest.pk, required=True)
    return render(
        request,
        "guests/partials/quick_guest_form.html",
        {
            "form": form,
            "select_id": select_id,
            "field_name": field_name,
            "title": _("Yangi mehmon"),
        },
    )


@role_required(*FRONT_OFFICE)
@tenant_login_required
def guest_detail(request, pk):
    guest = get_object_or_404(Guest, pk=pk, tenant=request.tenant)
    doc_form = GuestDocumentForm()
    note_form = GuestNoteForm()
    return render(
        request,
        "guests/guest_detail.html",
        {"guest": guest, "doc_form": doc_form, "note_form": note_form},
    )


@role_required(*FRONT_OFFICE)
@tenant_login_required
@require_http_methods(["GET", "POST"])
def guest_edit(request, pk):
    guest = get_object_or_404(Guest, pk=pk, tenant=request.tenant)
    form = GuestForm(request.POST or None, instance=guest, tenant=request.tenant)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Mehmon yangilandi."))
        return redirect("guests:detail", pk=guest.pk)
    return render(
        request, "guests/guest_form.html", {"form": form, "title": _("Mehmonni tahrirlash")}
    )


@role_required(*FRONT_OFFICE)
@tenant_login_required
@require_http_methods(["POST"])
def guest_add_document(request, pk):
    guest = get_object_or_404(Guest, pk=pk, tenant=request.tenant)
    form = GuestDocumentForm(request.POST, request.FILES)
    if form.is_valid():
        doc = form.save(commit=False)
        doc.tenant = request.tenant
        doc.guest = guest
        doc.save()
        messages.success(request, _("Hujjat qo‘shildi."))
    else:
        messages.error(request, _("Hujjat saqlanmadi."))
    return redirect("guests:detail", pk=guest.pk)


@role_required(*FRONT_OFFICE)
@tenant_login_required
@require_http_methods(["POST"])
def guest_add_note(request, pk):
    guest = get_object_or_404(Guest, pk=pk, tenant=request.tenant)
    form = GuestNoteForm(request.POST)
    if form.is_valid():
        note = form.save(commit=False)
        note.tenant = request.tenant
        note.guest = guest
        note.created_by = request.user
        note.save()
        messages.success(request, _("Izoh qo‘shildi."))
    return redirect("guests:detail", pk=guest.pk)


@role_required(*FRONT_OFFICE)
@tenant_login_required
def company_list(request):
    companies = Company.objects.filter(tenant=request.tenant)
    return render(request, "guests/company_list.html", {"companies": companies})


@role_required(*FRONT_OFFICE)
@tenant_login_required
def company_detail(request, pk):
    company = get_object_or_404(Company, pk=pk, tenant=request.tenant)
    invoices = (
        CompanyInvoice.objects.filter(tenant=request.tenant, company=company)
        .order_by("-issued_at")[:50]
    )
    reservations = (
        Reservation.objects.filter(tenant=request.tenant, company=company)
        .select_related("guest", "room")
        .order_by("-check_in")[:40]
    )
    return render(
        request,
        "guests/company_detail.html",
        {
            "company": company,
            "invoices": invoices,
            "reservations": reservations,
            "open_ar": company_open_balance(company),
        },
    )


@role_required(*FRONT_OFFICE)
@tenant_login_required
@require_http_methods(["GET", "POST"])
def company_create(request):
    form = CompanyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        company = form.save(commit=False)
        company.tenant = request.tenant
        company.save()
        messages.success(request, _("Kompaniya qo‘shildi."))
        return redirect("guests:company_detail", pk=company.pk)
    return render(request, "guests/company_form.html", {"form": form})


@role_required(*FRONT_OFFICE)
@tenant_login_required
@require_http_methods(["GET", "POST"])
def company_quick_create(request):
    """Inline HTMX create used from reservation/group forms."""
    select_id = request.GET.get("select_id") or request.POST.get("select_id") or "id_company"
    field_name = request.GET.get("field_name") or request.POST.get("field_name") or "company"
    form = CompanyQuickForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        company = Company.objects.create(
            tenant=request.tenant,
            name=form.cleaned_data["name"],
            phone=form.cleaned_data.get("phone") or "",
            inn=form.cleaned_data.get("inn") or "",
        )
        qs = Company.objects.filter(tenant=request.tenant, is_active=True).order_by("name")
        return oob_select_response(select_id, field_name, qs, company.pk)
    return render(
        request,
        "guests/partials/quick_company_form.html",
        {
            "form": form,
            "select_id": select_id,
            "field_name": field_name,
            "title": _("Yangi kompaniya"),
        },
    )
