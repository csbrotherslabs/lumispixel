from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "accounts"

urlpatterns = [
    path("get-started/", views.get_started, name="get-started"),
    path("signup/client/", views.client_signup, name="client-signup"),
    path("signup/photographer/", views.photographer_signup, name="photographer-signup"),
    path("accounts/login/", views.login_view, name="login"),
    path("accounts/logout/", views.logout_view, name="logout"),

    path(
        "accounts/password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset_form.html",
            email_template_name="accounts/email/password_reset_email.txt",
            html_email_template_name="accounts/email/password_reset_email.html",
            subject_template_name="accounts/email/password_reset_subject.txt",
            success_url=reverse_lazy("accounts:password-reset-done"),
        ),
        name="password-reset",
    ),
    path(
        "accounts/password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html"),
        name="password-reset-done",
    ),
    path(
        "accounts/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password-reset-complete"),
        ),
        name="password-reset-confirm",
    ),
    path(
        "accounts/reset/done/",
        auth_views.PasswordResetCompleteView.as_view(template_name="accounts/password_reset_complete.html"),
        name="password-reset-complete",
    ),
    path("accounts/post-login/", views.post_login_redirect, name="post-login-redirect"),
    path("accounts/verify-email/", views.verification_pending, name="verification-pending"),
    path("accounts/verify-email/<uidb64>/<token>/", views.verify_email, name="verify-email"),
    path("accounts/resend-verification/", views.resend_verification, name="resend-verification"),
    path("accounts/password-reset-required/", views.placeholder_view, {"title": "Password reset required"}, name="password-reset-required"),
    path("accounts/email-verification-required/", views.verification_pending, name="email-verification-required"),
    path("accounts/onboarding/photographer/", views.photographer_onboarding_entry, name="photographer-onboarding"),
    path("accounts/enable-photographer-workspace/", views.enable_photographer_workspace, name="enable-photographer-workspace"),
    path("accounts/enable-client-profile/", views.enable_client_profile, name="enable-client-profile"),
    path("accounts/find-photos/", views.placeholder_view, {"title": "Find My Photos"}, name="find-photos-placeholder"),
    path("accounts/marketplace-request/", views.placeholder_view, {"title": "Marketplace Request"}, name="marketplace-request-placeholder"),
    path("accounts/dashboard/client/", views.client_dashboard, name="client-dashboard"),
    path("accounts/dashboard/photographer/", views.placeholder_view, {"title": "Photographer dashboard"}, name="photographer-dashboard"),
    path("accounts/dashboard/marketplace/", views.placeholder_view, {"title": "Marketplace"}, name="marketplace-dashboard"),
    path("accounts/dashboard/operations/", views.placeholder_view, {"title": "Operations dashboard"}, name="operations-dashboard"),
]
