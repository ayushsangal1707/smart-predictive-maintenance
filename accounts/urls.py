from django.urls import path

from core.rate_limit import rate_limit

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", rate_limit("login", max_attempts=8, window_seconds=300)(views.AccountLoginView.as_view()), name="login"),
    path("logout/", views.AccountLogoutView.as_view(), name="logout"),
    path("register/", rate_limit("register", max_attempts=5, window_seconds=600)(views.register_view), name="register"),
    path("profile/", views.profile_view, name="profile"),
    path("settings/", views.settings_view, name="settings"),

    # Change password (logged-in user)
    path("password/change/", views.AccountPasswordChangeView.as_view(), name="password_change"),
    path("password/change/done/", views.AccountPasswordChangeDoneView.as_view(), name="password_change_done"),

    # Forgot password (logged-out user, emailed reset link)
    path(
        "password/reset/",
        rate_limit("password_reset", max_attempts=5, window_seconds=600)(views.AccountPasswordResetView.as_view()),
        name="password_reset",
    ),
    path("password/reset/done/", views.AccountPasswordResetDoneView.as_view(), name="password_reset_done"),
    path(
        "password/reset/confirm/<uidb64>/<token>/",
        views.AccountPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path("password/reset/complete/", views.AccountPasswordResetCompleteView.as_view(), name="password_reset_complete"),
]
