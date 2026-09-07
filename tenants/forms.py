from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from properties.models import Property

from .models import MembershipProperty, TenantMembership

User = get_user_model()


def _property_field(tenant):
    return forms.ModelMultipleChoiceField(
        queryset=Property.objects.filter(tenant=tenant, is_active=True).order_by("name"),
        required=False,
        label=_("Filiallar"),
        help_text=_("Bo‘sh qoldirilsa — barcha filiallarga ruxsat."),
    )


def save_membership_properties(membership, properties):
    selected_ids = {p.pk for p in properties}
    MembershipProperty.objects.filter(membership=membership).exclude(
        property_id__in=selected_ids
    ).delete()
    for prop in properties:
        MembershipProperty.objects.get_or_create(membership=membership, property=prop)


class StaffInviteForm(forms.Form):
    username = forms.CharField(max_length=150, label=_("Login"))
    email = forms.EmailField(required=False, label=_("Email"))
    password = forms.CharField(widget=forms.PasswordInput, min_length=8, label=_("Parol"))
    first_name = forms.CharField(required=False, max_length=150, label=_("Ism"))
    last_name = forms.CharField(required=False, max_length=150, label=_("Familiya"))
    role = forms.ChoiceField(choices=TenantMembership.Role.choices, label=_("Rol"))

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        if tenant is not None:
            self.fields["properties"] = _property_field(tenant)


class StaffRoleForm(forms.ModelForm):
    class Meta:
        model = TenantMembership
        fields = ("role", "is_active")
        labels = {"role": _("Rol"), "is_active": _("Faol")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.tenant_id:
            self.fields["properties"] = _property_field(self.instance.tenant)
            self.fields["properties"].initial = list(self.instance.assigned_property_ids())

    def save(self, commit=True):
        membership = super().save(commit=commit)
        if commit and "properties" in self.cleaned_data:
            save_membership_properties(membership, self.cleaned_data["properties"])
        return membership
