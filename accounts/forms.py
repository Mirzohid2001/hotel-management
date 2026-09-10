from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class ProfileForm(forms.ModelForm):
    new_password = forms.CharField(
        label=_("Yangi parol"),
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=_("Bo‘sh qoldirsangiz — parol o‘zgarmaydi."),
    )
    new_password_confirm = forms.CharField(
        label=_("Parolni takrorlang"),
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone")
        labels = {
            "first_name": _("Ism"),
            "last_name": _("Familiya"),
            "email": _("Email"),
            "phone": _("Telefon"),
        }

    def clean(self):
        cleaned = super().clean()
        pwd = (cleaned.get("new_password") or "").strip()
        confirm = (cleaned.get("new_password_confirm") or "").strip()
        if pwd or confirm:
            if len(pwd) < 8:
                self.add_error("new_password", _("Parol kamida 8 belgidan iborat bo‘lsin."))
            if pwd != confirm:
                self.add_error("new_password_confirm", _("Parollar mos kelmadi."))
        cleaned["new_password"] = pwd
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        pwd = self.cleaned_data.get("new_password") or ""
        if pwd:
            user.set_password(pwd)
        if commit:
            user.save()
        return user
