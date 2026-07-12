from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordChangeDoneView,
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from django.urls import reverse_lazy
from django.shortcuts import redirect, render

from .forms import (
    ProfileUpdateForm,
    RegistrationForm,
    SettingsForm,
    StyledAuthenticationForm,
    StyledPasswordChangeForm,
    StyledPasswordResetForm,
    StyledSetPasswordForm,
)


# ---------------------------------------------------------------------------
# Login / Logout
# ---------------------------------------------------------------------------

class AccountLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = StyledAuthenticationForm
    redirect_authenticated_user = True


class AccountLogoutView(LogoutView):
    """
    Django's LogoutView only accepts POST (by design, to prevent logout via
    a GET request/link, which is a CSRF-style footgun). The navbar therefore
    submits a small <form method="post"> rather than a plain <a> link.
    """
    next_page = reverse_lazy("accounts:login")


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

def register_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, "Account created successfully. Welcome!")
            return redirect("accounts:profile")
    else:
        form = RegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@login_required
def profile_view(request):
    profile = request.user.profile

    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("accounts:profile")
    else:
        form = ProfileUpdateForm(instance=profile, user=request.user)

    return render(request, "accounts/profile.html", {"form": form, "profile": profile})


# ---------------------------------------------------------------------------
# Settings (dark mode default, email notification opt-in/out)
# ---------------------------------------------------------------------------

@login_required
def settings_view(request):
    if request.method == "POST":
        form = SettingsForm(request.POST, instance=request.user.preference)
        if form.is_valid():
            form.save()
            messages.success(request, "Settings updated.")
            return redirect("accounts:settings")
    else:
        form = SettingsForm(instance=request.user.preference)

    return render(request, "accounts/settings.html", {"form": form})


# ---------------------------------------------------------------------------
# Change Password (user already logged in and knows their current password)
# ---------------------------------------------------------------------------

class AccountPasswordChangeView(PasswordChangeView):
    template_name = "accounts/password_change_form.html"
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy("accounts:password_change_done")


class AccountPasswordChangeDoneView(PasswordChangeDoneView):
    template_name = "accounts/password_change_done.html"


# ---------------------------------------------------------------------------
# Forgot Password (user is logged out, resets via emailed link)
# ---------------------------------------------------------------------------

class AccountPasswordResetView(PasswordResetView):
    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/password_reset_email.html"
    subject_template_name = "accounts/password_reset_subject.txt"
    form_class = StyledPasswordResetForm
    success_url = reverse_lazy("accounts:password_reset_done")


class AccountPasswordResetDoneView(PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class AccountPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    form_class = StyledSetPasswordForm
    success_url = reverse_lazy("accounts:password_reset_complete")


class AccountPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"
