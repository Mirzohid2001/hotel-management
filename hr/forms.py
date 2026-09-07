from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Employee, SalaryAdvance


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = (
            "full_name",
            "position",
            "salary_type",
            "base_salary",
            "hire_date",
            "phone",
            "is_active",
        )
        labels = {
            "full_name": _("F.I.Sh."),
            "position": _("Lavozim"),
            "salary_type": _("Maosh turi"),
            "base_salary": _("Asosiy maosh"),
            "hire_date": _("Ishga kirgan sana"),
            "phone": _("Telefon"),
            "is_active": _("Faol"),
        }
        widgets = {"hire_date": forms.DateInput(attrs={"type": "date"})}


class SalaryAdvanceForm(forms.ModelForm):
    class Meta:
        model = SalaryAdvance
        fields = ("employee", "amount", "advance_date", "note")
        labels = {
            "employee": _("Xodim"),
            "amount": _("Summa"),
            "advance_date": _("Sana"),
            "note": _("Izoh"),
        }
        widgets = {"advance_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["employee"].queryset = Employee.objects.filter(
                tenant=tenant, is_active=True
            )


class EmployeeAdvanceForm(forms.Form):
    amount = forms.DecimalField(
        min_value=0.01,
        max_digits=14,
        decimal_places=2,
        label=_("Summa"),
    )
    advance_date = forms.DateField(
        label=_("Sana"),
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False,
    )
    note = forms.CharField(label=_("Izoh"), required=False, max_length=255)


class PayrollItemAdjustForm(forms.Form):
    bonus = forms.DecimalField(
        min_value=0,
        max_digits=14,
        decimal_places=2,
        label=_("Bonus"),
        initial=0,
    )
    deduction = forms.DecimalField(
        min_value=0,
        max_digits=14,
        decimal_places=2,
        label=_("Ushlama"),
        initial=0,
    )
