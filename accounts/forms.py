from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.contrib.auth.models import User

from core.constants import ROLE_CHOICES
from .models import UserPreference, UserProfile


def _bootstrapify(fields):
    """Adds Bootstrap's form-control class to every field's widget."""
    for field in fields.values():
        existing = field.widget.attrs.get("class", "")
        field.widget.attrs["class"] = (existing + " form-control").strip()


class RegistrationForm(UserCreationForm):
    """
    Extends Django's UserCreationForm to also collect email + role +
    BHEL-specific fields, and saves them onto the auto-created UserProfile
    (see accounts/signals.py) in one save() call.
    """

    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=ROLE_CHOICES)
    employee_id = forms.CharField(max_length=30, required=False)
    department = forms.CharField(max_length=100, required=False)
    phone = forms.CharField(max_length=20, required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "email", "first_name", "last_name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrapify(self.fields)
        # Add a live password-strength meter (see static/js/auth.js) to the
        # first password field only.
        self.fields["password1"].widget.attrs["data-password-strength"] = "true"

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            # UserProfile already exists thanks to the post_save signal;
            # update it with the extra fields collected on this form.
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = self.cleaned_data["role"]
            profile.employee_id = self.cleaned_data.get("employee_id", "")
            profile.department = self.cleaned_data.get("department", "")
            profile.phone = self.cleaned_data.get("phone", "")
            profile.save()
        return user


class ProfileUpdateForm(forms.ModelForm):
    """Lets a logged-in user update their own non-security profile details."""

    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=True)

    class Meta:
        model = UserProfile
        fields = ["employee_id", "department", "phone"]

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["first_name"].initial = user.first_name
            self.fields["last_name"].initial = user.last_name
            self.fields["email"].initial = user.email
        _bootstrapify(self.fields)

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.user is not None:
            self.user.first_name = self.cleaned_data["first_name"]
            self.user.last_name = self.cleaned_data["last_name"]
            self.user.email = self.cleaned_data["email"]
            if commit:
                self.user.save()
        if commit:
            profile.save()
        return profile


# ---------------------------------------------------------------------------
# Bootstrap-styled wrappers around Django's built-in auth forms.
# Subclassing (rather than rewriting them) keeps all of Django's validation
# and security behavior (rate limiting hooks, password validators, etc.)
# intact — only widget attrs are changed.
# ---------------------------------------------------------------------------

class StyledAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrapify(self.fields)
        self.fields["username"].widget.attrs["autofocus"] = True


class StyledPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrapify(self.fields)
        self.fields["new_password1"].widget.attrs["data-password-strength"] = "true"


class StyledPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrapify(self.fields)


class StyledSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrapify(self.fields)
        self.fields["new_password1"].widget.attrs["data-password-strength"] = "true"


class SettingsForm(forms.ModelForm):
    class Meta:
        model = UserPreference
        fields = ["dark_mode_default", "email_notifications_enabled"]
        widgets = {
            "dark_mode_default": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "email_notifications_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
