from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST

from core.mixins import feature_required, role_required
from core.roles import FINANCE

from .forms import (
    BaseCurrencyForm,
    ExchangeRateForm,
    ExpenseCategoryForm,
    ExpenseForm,
    ProfitPartnerForm,
    ProfitResetForm,
    ProfitWithdrawalForm,
    VendorForm,
)
from tenants.models import ExchangeRate
from core.currency import CURRENCY_CHOICES, DEFAULT_RATES_TO_UZS, get_rate_to_base
from django.utils import timezone
from .models import Expense, ExpenseCategory, ProfitPartner, ProfitPeriod, Vendor
from .profit import (
    active_share_total,
    build_partner_ledger,
    ensure_open_period,
    record_withdrawal,
    reset_profit_period,
)
from .services import (
    approve_expense,
    assert_expense_editable,
    delete_expense,
    mark_expense_paid,
    reject_expense,
    reopen_expense,
)


def _expense_branch_blocked(request, expense) -> bool:
    """Active filial tanlanganda boshqa filial rasxodiga ruxsat bermaslik."""
    hotel = getattr(request, "active_property", None)
    if hotel is not None and expense.hotel_id and expense.hotel_id != hotel.pk:
        messages.error(request, _("Bu rasxod boshqa filialga tegishli."))
        return True
    return False


def _render_expense_row(request, expense):
    expense = Expense.objects.select_related(
        "category", "vendor", "approved_by", "rejected_by", "paid_by"
    ).get(pk=expense.pk)
    return render(
        request,
        "finance/partials/expense_row.html",
        {"e": expense},
    )


def _parse_date(value: str):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


@feature_required("expenses")
@role_required(*FINANCE)
def expense_list(request):
    status = request.GET.get("status", "")
    q = (request.GET.get("q") or "").strip()
    category_id = request.GET.get("category", "")
    vendor_id = request.GET.get("vendor", "")
    method = request.GET.get("method", "")
    date_from = _parse_date(request.GET.get("date_from", ""))
    date_to = _parse_date(request.GET.get("date_to", ""))

    expenses = Expense.objects.filter(tenant=request.tenant).select_related(
        "category", "vendor", "approved_by", "rejected_by", "paid_by", "hotel"
    )
    hotel = getattr(request, "active_property", None)
    if hotel is not None:
        expenses = expenses.filter(hotel=hotel)
    if status:
        expenses = expenses.filter(status=status)
    if q:
        expenses = expenses.filter(
            Q(title__icontains=q)
            | Q(notes__icontains=q)
            | Q(category__name__icontains=q)
            | Q(vendor__name__icontains=q)
        )
    if category_id.isdigit():
        expenses = expenses.filter(category_id=int(category_id))
    if vendor_id.isdigit():
        expenses = expenses.filter(vendor_id=int(vendor_id))
    if method in dict(Expense.PaymentMethod.choices):
        expenses = expenses.filter(payment_method=method)
    if date_from:
        expenses = expenses.filter(expense_date__gte=date_from)
    if date_to:
        expenses = expenses.filter(expense_date__lte=date_to)

    total = expenses.aggregate(s=Sum("amount_base"))["s"] or Decimal("0")
    count = expenses.count()

    return render(
        request,
        "finance/expense_list.html",
        {
            "expenses": expenses[:200],
            "status": status,
            "statuses": Expense.Status.choices,
            "q": q,
            "category_id": category_id,
            "vendor_id": vendor_id,
            "method": method,
            "methods": Expense.PaymentMethod.choices,
            "date_from": date_from.isoformat() if date_from else "",
            "date_to": date_to.isoformat() if date_to else "",
            "categories": ExpenseCategory.objects.filter(tenant=request.tenant).order_by("name"),
            "vendors": Vendor.objects.filter(tenant=request.tenant).order_by("name"),
            "filter_total": total,
            "filter_count": count,
        },
    )


@feature_required("expenses")
@role_required(*FINANCE)
@require_http_methods(["GET", "POST"])
def expense_create(request):
    hotel = getattr(request, "active_property", None)
    if hotel is None:
        messages.error(request, _("Rasxod uchun avval filial tanlang."))
        return redirect("finance:list")
    form = ExpenseForm(request.POST or None, request.FILES or None, tenant=request.tenant)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.tenant = request.tenant
        obj.hotel = hotel
        obj.created_by = request.user
        obj.save()
        messages.success(request, _("Rasxod qo‘shildi."))
        return redirect("finance:list")
    return render(
        request,
        "finance/expense_form.html",
        {"form": form, "title": _("Yangi rasxod"), "hotel": hotel},
    )


@feature_required("expenses")
@role_required(*FINANCE)
@require_http_methods(["GET", "POST"])
def expense_edit(request, pk):
    expense = get_object_or_404(Expense, pk=pk, tenant=request.tenant)
    hotel = getattr(request, "active_property", None)
    if hotel is not None and expense.hotel_id and expense.hotel_id != hotel.pk:
        messages.error(request, _("Bu rasxod boshqa filialga tegishli."))
        return redirect("finance:list")
    try:
        assert_expense_editable(expense)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("finance:list")
    form = ExpenseForm(
        request.POST or None,
        request.FILES or None,
        instance=expense,
        tenant=request.tenant,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Rasxod yangilandi."))
        return redirect("finance:list")
    return render(
        request,
        "finance/expense_form.html",
        {"form": form, "title": _("Rasxodni tahrirlash"), "expense": expense, "hotel": hotel},
    )


@feature_required("expenses")
@role_required(*FINANCE)
@require_POST
def expense_approve(request, pk):
    expense = get_object_or_404(Expense, pk=pk, tenant=request.tenant)
    if _expense_branch_blocked(request, expense):
        return redirect("finance:list")
    try:
        approve_expense(expense, request.user)
        messages.success(request, _("Tasdiqlandi."))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    if request.htmx:
        return _render_expense_row(request, expense)
    return redirect("finance:list")


@feature_required("expenses")
@role_required(*FINANCE)
@require_POST
def expense_reject(request, pk):
    expense = get_object_or_404(Expense, pk=pk, tenant=request.tenant)
    if _expense_branch_blocked(request, expense):
        return redirect("finance:list")
    try:
        reject_expense(expense, request.user, reason=request.POST.get("reason", ""))
        messages.success(request, _("Rad etildi."))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    if request.htmx:
        return _render_expense_row(request, expense)
    return redirect("finance:list")


@feature_required("expenses")
@role_required(*FINANCE)
@require_POST
def expense_pay(request, pk):
    expense = get_object_or_404(Expense, pk=pk, tenant=request.tenant)
    if _expense_branch_blocked(request, expense):
        return redirect("finance:list")
    try:
        mark_expense_paid(expense, request.user)
        messages.success(request, _("To‘langan deb belgilandi."))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    if request.htmx:
        return _render_expense_row(request, expense)
    return redirect("finance:list")


@feature_required("expenses")
@role_required(*FINANCE)
@require_POST
def expense_reopen(request, pk):
    expense = get_object_or_404(Expense, pk=pk, tenant=request.tenant)
    if _expense_branch_blocked(request, expense):
        return redirect("finance:list")
    try:
        reopen_expense(expense, request.user)
        messages.success(request, _("Qoralamaga qaytarildi."))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    if request.htmx:
        return _render_expense_row(request, expense)
    return redirect("finance:list")


@feature_required("expenses")
@role_required(*FINANCE)
@require_POST
def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk, tenant=request.tenant)
    if _expense_branch_blocked(request, expense):
        return redirect("finance:list")
    try:
        delete_expense(expense, request.user)
        messages.success(request, _("Rasxod o‘chirildi."))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        if request.htmx:
            return _render_expense_row(request, expense)
        return redirect("finance:list")
    if request.htmx:
        from django.http import HttpResponse

        return HttpResponse("")
    return redirect("finance:list")


@feature_required("expenses")
@role_required(*FINANCE)
def category_list(request):
    cats = ExpenseCategory.objects.filter(tenant=request.tenant)
    vendors = Vendor.objects.filter(tenant=request.tenant)
    return render(
        request,
        "finance/setup_list.html",
        {"categories": cats, "vendors": vendors},
    )


@feature_required("expenses")
@role_required(*FINANCE)
@require_http_methods(["GET", "POST"])
def category_create(request):
    form = ExpenseCategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.tenant = request.tenant
        obj.save()
        messages.success(request, _("Kategoriya qo‘shildi."))
        return redirect("finance:setup")
    return render(
        request,
        "finance/expense_form.html",
        {"form": form, "title": _("Kategoriya"), "cancel_url_name": "finance:setup"},
    )


@feature_required("expenses")
@role_required(*FINANCE)
@require_http_methods(["GET", "POST"])
def category_edit(request, pk):
    category = get_object_or_404(ExpenseCategory, pk=pk, tenant=request.tenant)
    form = ExpenseCategoryForm(request.POST or None, instance=category)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Kategoriya yangilandi."))
        return redirect("finance:setup")
    return render(
        request,
        "finance/expense_form.html",
        {
            "form": form,
            "title": _("Kategoriyani tahrirlash"),
            "cancel_url_name": "finance:setup",
        },
    )


@feature_required("expenses")
@role_required(*FINANCE)
@require_POST
def category_toggle(request, pk):
    category = get_object_or_404(ExpenseCategory, pk=pk, tenant=request.tenant)
    category.is_active = not category.is_active
    category.save(update_fields=["is_active", "updated_at"])
    messages.success(
        request,
        _("Kategoriya faol.") if category.is_active else _("Kategoriya o‘chirildi (faol emas)."),
    )
    return redirect("finance:setup")


@feature_required("expenses")
@role_required(*FINANCE)
@require_http_methods(["GET", "POST"])
def vendor_create(request):
    form = VendorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.tenant = request.tenant
        obj.save()
        messages.success(request, _("Yetkazib beruvchi qo‘shildi."))
        return redirect("finance:setup")
    return render(
        request,
        "finance/expense_form.html",
        {"form": form, "title": _("Yetkazib beruvchi"), "cancel_url_name": "finance:setup"},
    )


@feature_required("expenses")
@role_required(*FINANCE)
@require_http_methods(["GET", "POST"])
def vendor_edit(request, pk):
    vendor = get_object_or_404(Vendor, pk=pk, tenant=request.tenant)
    form = VendorForm(request.POST or None, instance=vendor)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Yetkazib beruvchi yangilandi."))
        return redirect("finance:setup")
    return render(
        request,
        "finance/expense_form.html",
        {
            "form": form,
            "title": _("Yetkazib beruvchini tahrirlash"),
            "cancel_url_name": "finance:setup",
        },
    )


@feature_required("expenses")
@role_required(*FINANCE)
@require_POST
def vendor_toggle(request, pk):
    vendor = get_object_or_404(Vendor, pk=pk, tenant=request.tenant)
    vendor.is_active = not vendor.is_active
    vendor.save(update_fields=["is_active", "updated_at"])
    messages.success(
        request,
        _("Yetkazib beruvchi faol.")
        if vendor.is_active
        else _("Yetkazib beruvchi o‘chirildi (faol emas)."),
    )
    return redirect("finance:setup")


@feature_required("pnl")
@role_required(*FINANCE)
def profit_share(request):
    ledger = build_partner_ledger(tenant=request.tenant)
    closed = ProfitPeriod.objects.filter(tenant=request.tenant, ended_on__isnull=False)[:8]
    return render(
        request,
        "finance/profit_share.html",
        {
            "ledger": ledger,
            "share_total": active_share_total(request.tenant),
            "closed_periods": closed,
        },
    )


@feature_required("pnl")
@role_required(*FINANCE)
def profit_share_print(request):
    ledger = build_partner_ledger(tenant=request.tenant)
    return render(
        request,
        "finance/profit_share_print.html",
        {
            "ledger": ledger,
            "tenant_name": getattr(request.tenant, "name", "") or str(request.tenant),
            "currency": request.tenant.currency or "UZS",
        },
    )


@feature_required("pnl")
@role_required(*FINANCE)
@require_http_methods(["GET", "POST"])
def profit_partner_create(request):
    form = ProfitPartnerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.tenant = request.tenant
        obj.save()
        ensure_open_period(request.tenant)
        messages.success(request, _("Sherik qo‘shildi."))
        total = active_share_total(request.tenant)
        if total != Decimal("100"):
            messages.warning(
                request,
                _("Faol ulushlar yig‘indisi %(t)s%% (ideal 100%%).") % {"t": total},
            )
        return redirect("finance:profit_share")
    return render(
        request,
        "finance/expense_form.html",
        {
            "form": form,
            "title": _("Yangi sherik"),
            "cancel_url_name": "finance:profit_share",
        },
    )


@feature_required("pnl")
@role_required(*FINANCE)
@require_http_methods(["GET", "POST"])
def profit_partner_edit(request, pk):
    partner = get_object_or_404(ProfitPartner, pk=pk, tenant=request.tenant)
    form = ProfitPartnerForm(request.POST or None, instance=partner)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Sherik yangilandi."))
        total = active_share_total(request.tenant)
        if total != Decimal("100"):
            messages.warning(
                request,
                _("Faol ulushlar yig‘indisi %(t)s%% (ideal 100%%).") % {"t": total},
            )
        return redirect("finance:profit_share")
    return render(
        request,
        "finance/expense_form.html",
        {
            "form": form,
            "title": _("Sherikni tahrirlash"),
            "cancel_url_name": "finance:profit_share",
        },
    )


@feature_required("pnl")
@role_required(*FINANCE)
@require_http_methods(["GET", "POST"])
def profit_withdraw(request):
    ledger = build_partner_ledger(tenant=request.tenant)
    initial = {
        "paid_on": date.today().isoformat(),
        "payment_method": "cash",
    }
    partner_id = request.GET.get("partner")
    selected_remaining = None
    if partner_id and partner_id.isdigit():
        pid = int(partner_id)
        initial["partner"] = pid
        row = next((r for r in ledger["rows"] if r["partner"].pk == pid), None)
        if row and row["remaining"] > 0:
            initial["amount"] = row["remaining"]
            selected_remaining = row["remaining"]
    form = ProfitWithdrawalForm(
        request.POST or None, tenant=request.tenant, initial=initial
    )
    if request.method == "POST" and form.is_valid():
        try:
            record_withdrawal(
                request.tenant,
                request.user,
                partner=form.cleaned_data["partner"],
                amount=form.cleaned_data["amount"],
                paid_on=form.cleaned_data["paid_on"],
                payment_method=form.cleaned_data["payment_method"],
                note=form.cleaned_data.get("note") or "",
                allow_overdraw=form.cleaned_data.get("allow_overdraw") or False,
                currency=form.cleaned_data.get("currency"),
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, _("Foyda olish yozildi."))
            return redirect("finance:profit_share")
    return render(
        request,
        "finance/profit_withdraw.html",
        {
            "form": form,
            "ledger": ledger,
            "selected_remaining": selected_remaining,
        },
    )


@feature_required("pnl")
@role_required(*FINANCE)
@require_http_methods(["GET", "POST"])
def profit_reset(request):
    ledger = build_partner_ledger(tenant=request.tenant)
    form = ProfitResetForm(
        request.POST or None,
        initial={"ended_on": ledger["end"].isoformat()},
    )
    if request.method == "POST" and form.is_valid():
        try:
            closed, fresh = reset_profit_period(
                request.tenant,
                request.user,
                ended_on=form.cleaned_data["ended_on"],
                note=form.cleaned_data.get("note") or "",
                restart_today=form.cleaned_data.get("restart_today") or False,
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(
                request,
                _(
                    "Davr yopildi (%(start)s → %(end)s). Yangi hisob %(fresh)s dan boshlanadi."
                )
                % {
                    "start": closed.started_on,
                    "end": closed.ended_on,
                    "fresh": fresh.started_on,
                },
            )
            return redirect("finance:profit_share")
    return render(
        request,
        "finance/profit_reset.html",
        {"form": form, "ledger": ledger},
    )


@role_required(*FINANCE)
@require_http_methods(["GET", "POST"])
def exchange_rates(request):
    """Bazaviy valyuta + USD/EUR kurslari — butun hisob-kitob shu asosda."""
    from core.cbu import (
        CBUFetchError,
        ensure_today_cbu_rates,
        has_fresh_cbu_rates,
        sync_cbu_rates_for_tenant,
    )

    tenant = request.tenant
    # Sahifa ochilganda bugungi CBU kursi yo‘q bo‘lsa — avtomatik yuklash
    if request.method == "GET":
        auto = ensure_today_cbu_rates(tenant)
        if auto and (auto.get("created") or auto.get("updated")):
            messages.info(
                request,
                _("Markaziy bank kursi yangilandi (%(d)s).")
                % {"d": auto["effective_on"]},
            )

    base_form = BaseCurrencyForm(request.POST or None, instance=tenant, prefix="base")
    rate_form = ExchangeRateForm(
        None if request.POST and request.POST.get("form") != "rate" else request.POST,
        tenant=tenant,
        prefix="rate",
        initial={
            "effective_on": timezone.localdate(),
            "currency": "USD" if tenant.currency != "USD" else "EUR",
        },
    )

    if request.method == "POST":
        which = request.POST.get("form")
        if which == "base" and base_form.is_valid():
            base_form.save()
            messages.success(
                request,
                _("Bazaviy valyuta: %(c)s") % {"c": tenant.currency},
            )
            return redirect("finance:exchange_rates")
        if which == "cbu":
            try:
                info = sync_cbu_rates_for_tenant(tenant, force=True)
                messages.success(
                    request,
                    _("CBU: %(d)s — %(rates)s")
                    % {
                        "d": info["effective_on"],
                        "rates": ", ".join(
                            f"1 {c} = {r} {info['base_currency']}"
                            for c, r in info["rates"].items()
                            if c != info["base_currency"]
                        ),
                    },
                )
            except CBUFetchError as exc:
                messages.error(request, "; ".join(exc.messages))
            return redirect("finance:exchange_rates")
        if which == "rate":
            rate_form = ExchangeRateForm(request.POST, tenant=tenant, prefix="rate")
            if rate_form.is_valid():
                row = rate_form.save(commit=False)
                row.tenant = tenant
                row.base_currency = tenant.currency or "UZS"
                row.save()
                messages.success(
                    request,
                    _("Kurs saqlandi: 1 %(c)s = %(r)s %(b)s")
                    % {
                        "c": row.currency,
                        "r": row.rate,
                        "b": row.base_currency,
                    },
                )
                return redirect("finance:exchange_rates")

    rates = ExchangeRate.objects.filter(tenant=tenant).order_by(
        "-effective_on", "currency"
    )[:60]
    today = timezone.localdate()
    live = []
    for code, label in CURRENCY_CHOICES:
        if code == (tenant.currency or "UZS"):
            continue
        live.append(
            {
                "code": code,
                "label": label,
                "rate": get_rate_to_base(tenant, code, on_date=today),
            }
        )

    cbu_today = has_fresh_cbu_rates(tenant)

    return render(
        request,
        "finance/exchange_rates.html",
        {
            "base_form": base_form,
            "rate_form": rate_form,
            "rates": rates,
            "live": live,
            "base_currency": tenant.currency or "UZS",
            "defaults_hint": DEFAULT_RATES_TO_UZS,
            "cbu_today": cbu_today,
            "today": today,
        },
    )


@role_required(*FINANCE)
@require_POST
def exchange_rate_delete(request, pk):
    row = get_object_or_404(ExchangeRate, pk=pk, tenant=request.tenant)
    row.delete()
    messages.success(request, _("Kurs o‘chirildi."))
    return redirect("finance:exchange_rates")
