from django.utils.translation import gettext as _
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from core.mixins import feature_required, role_required
from core.roles import HR

from .forms import EmployeeAdvanceForm, EmployeeForm, PayrollItemAdjustForm, SalaryAdvanceForm
from .models import Employee, PayrollItem, PayrollPeriod, SalaryAdvance, SalaryPayment
from .services import (
    create_advance,
    finalize_payroll,
    generate_payroll,
    mark_item_paid,
    open_advance_total,
    pay_all_unpaid,
    pay_employee_salary,
    salary_due_preview,
    settle_advance,
    sync_item_advances,
    update_payroll_item_amounts,
)


@feature_required("payroll")
@role_required(*HR)
def employee_list(request):
    employees = list(Employee.objects.filter(tenant=request.tenant))
    today = timezone.localdate()
    paid_ids = set(
        SalaryPayment.objects.filter(
            tenant=request.tenant,
            item__period__year=today.year,
            item__period__month=today.month,
        ).values_list("item__employee_id", flat=True)
    )
    rows = []
    for emp in employees:
        open_adv = open_advance_total(emp)
        rows.append(
            {
                "employee": emp,
                "open_advance": open_adv,
                "due_preview": salary_due_preview(emp),
                "paid_this_month": emp.pk in paid_ids,
            }
        )
    return render(request, "hr/employee_list.html", {"rows": rows})


@feature_required("payroll")
@role_required(*HR)
@require_http_methods(["GET", "POST"])
def employee_create(request):
    form = EmployeeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        emp = form.save(commit=False)
        emp.tenant = request.tenant
        emp.save()
        messages.success(request, _("Xodim qo‘shildi."))
        return redirect("hr:employees")
    return render(request, "hr/employee_form.html", {"form": form, "title": _("Yangi xodim")})


@feature_required("payroll")
@role_required(*HR)
@require_http_methods(["GET", "POST"])
def employee_edit(request, pk):
    emp = get_object_or_404(Employee, pk=pk, tenant=request.tenant)
    form = EmployeeForm(request.POST or None, instance=emp)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Xodim yangilandi."))
        return redirect("hr:employees")
    return render(request, "hr/employee_form.html", {"form": form, "title": _("Tahrirlash")})


@feature_required("payroll")
@role_required(*HR)
@require_http_methods(["GET", "POST"])
def employee_advance(request, pk):
    """Xodimdan to‘g‘ridan-to‘g‘ri avans — oddiy forma / modal."""
    emp = get_object_or_404(Employee, pk=pk, tenant=request.tenant, is_active=True)
    initial = {"advance_date": timezone.localdate()}
    form = EmployeeAdvanceForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            create_advance(
                request.tenant,
                emp,
                amount=form.cleaned_data["amount"],
                advance_date=form.cleaned_data.get("advance_date") or timezone.localdate(),
                note=form.cleaned_data.get("note") or "",
            )
            messages.success(
                request,
                _("%(name)s ga avans yozildi.") % {"name": emp.full_name},
            )
            return redirect("hr:employees")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    return render(
        request,
        "hr/employee_advance_form.html",
        {
            "form": form,
            "employee": emp,
            "title": _("Avans: %(name)s") % {"name": emp.full_name},
            "open_advance": open_advance_total(emp),
        },
    )


@feature_required("payroll")
@role_required(*HR)
@require_POST
def employee_pay(request, pk):
    emp = get_object_or_404(Employee, pk=pk, tenant=request.tenant)
    try:
        payment = pay_employee_salary(request.tenant, emp)
        messages.success(
            request,
            _("%(name)s ga %(amount)s to‘landi.")
            % {"name": emp.full_name, "amount": payment.amount},
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("hr:employees")


@feature_required("payroll")
@role_required(*HR)
def payroll_list(request):
    from decimal import Decimal
    from django.db.models import Sum

    # To‘lanmagan qatorlarda avans ushlanmasini yangilash
    unpaid_items = PayrollItem.objects.filter(
        tenant=request.tenant, payment__isnull=True
    ).select_related("employee", "period")
    for item in unpaid_items:
        if item.period.status != PayrollPeriod.Status.PAID:
            sync_item_advances(item)

    periods = PayrollPeriod.objects.filter(tenant=request.tenant).prefetch_related(
        Prefetch(
            "items",
            queryset=PayrollItem.objects.select_related("employee", "payment"),
        )
    )
    unpaid_qs = PayrollItem.objects.filter(
        tenant=request.tenant, payment__isnull=True
    )
    unpaid_count = unpaid_qs.count()
    unpaid_total = unpaid_qs.aggregate(s=Sum("net_amount"))["s"] or Decimal("0")
    return render(
        request,
        "hr/payroll_list.html",
        {
            "periods": periods,
            "period_count": periods.count(),
            "unpaid_count": unpaid_count,
            "unpaid_total": unpaid_total,
        },
    )


@feature_required("payroll")
@role_required(*HR)
@require_POST
def payroll_generate(request):
    today = timezone.localdate()
    try:
        period = generate_payroll(request.tenant, today.year, today.month)
        messages.success(request, _("Ish haqi yangilandi: %(p)s") % {"p": period})
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("hr:payroll_list")


@feature_required("payroll")
@role_required(*HR)
@require_POST
def payroll_finalize(request, pk):
    period = get_object_or_404(PayrollPeriod, pk=pk, tenant=request.tenant)
    try:
        finalize_payroll(period)
        messages.success(request, _("Yakunlandi: %(period)s") % {"period": period})
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("hr:payroll_list")


@feature_required("payroll")
@role_required(*HR)
@require_http_methods(["GET", "POST"])
def payroll_item_edit(request, item_id):
    item = get_object_or_404(
        PayrollItem.objects.select_related("employee", "period", "payment"),
        pk=item_id,
        tenant=request.tenant,
    )
    if SalaryPayment.objects.filter(item=item).exists():
        messages.error(request, _("To‘langan qatorni o‘zgartirib bo‘lmaydi."))
        return redirect("hr:payroll_list")

    form = PayrollItemAdjustForm(
        request.POST or None,
        initial={"bonus": item.bonus, "deduction": item.deduction},
    )
    if request.method == "POST" and form.is_valid():
        try:
            update_payroll_item_amounts(
                item,
                bonus=form.cleaned_data["bonus"],
                deduction=form.cleaned_data["deduction"],
            )
            messages.success(
                request,
                _("%(name)s: bonus/ushlama yangilandi (sof %(net)s).")
                % {"name": item.employee.full_name, "net": item.net_amount},
            )
            return redirect("hr:payroll_list")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    return render(
        request,
        "hr/payroll_item_form.html",
        {
            "form": form,
            "item": item,
            "title": _("Bonus / ushlama: %(name)s") % {"name": item.employee.full_name},
        },
    )


@feature_required("payroll")
@role_required(*HR)
@require_POST
def payroll_pay_item(request, item_id):
    item = get_object_or_404(PayrollItem, pk=item_id, tenant=request.tenant)
    try:
        mark_item_paid(item)
        messages.success(request, _("To‘landi."))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("hr:payroll_list")


@feature_required("payroll")
@role_required(*HR)
@require_POST
def payroll_pay_all(request):
    today = timezone.localdate()
    try:
        count = pay_all_unpaid(request.tenant, year=today.year, month=today.month)
        if count:
            messages.success(
                request, _("%(n)s ta oylik to‘landi.") % {"n": count}
            )
        else:
            messages.info(request, _("To‘lanadigan qator yo‘q."))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("hr:payroll_list")


@feature_required("payroll")
@role_required(*HR)
def advance_list(request):
    status = request.GET.get("status", "open")
    qs = SalaryAdvance.objects.filter(tenant=request.tenant).select_related(
        "employee", "applied_to_period"
    )
    if status == "open":
        qs = qs.filter(is_settled=False)
    elif status == "settled":
        qs = qs.filter(is_settled=True)
    return render(
        request,
        "hr/advance_list.html",
        {"advances": qs, "status": status},
    )


@feature_required("payroll")
@role_required(*HR)
@require_http_methods(["GET", "POST"])
def advance_create(request):
    form = SalaryAdvanceForm(request.POST or None, tenant=request.tenant)
    if request.method == "POST" and form.is_valid():
        try:
            create_advance(
                request.tenant,
                form.cleaned_data["employee"],
                amount=form.cleaned_data["amount"],
                advance_date=form.cleaned_data["advance_date"],
                note=form.cleaned_data.get("note") or "",
            )
            messages.success(request, _("Avans qo‘shildi."))
            return redirect("hr:advances")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    return render(
        request,
        "hr/advance_form.html",
        {"form": form, "title": _("Yangi avans")},
    )


@feature_required("payroll")
@role_required(*HR)
@require_POST
def advance_settle(request, pk):
    advance = get_object_or_404(SalaryAdvance, pk=pk, tenant=request.tenant)
    try:
        settle_advance(advance)
        messages.success(request, _("Avans yopildi."))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("hr:advances")
