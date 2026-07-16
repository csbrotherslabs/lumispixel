from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("get-started/", views.get_started, name="get-started"),
    path("signup/client/", views.client_signup, name="client-signup"),
    path("signup/photographer/", views.photographer_signup, name="photographer-signup"),
    path("accounts/login/", views.login_view, name="login"),
    path("accounts/logout/", views.logout_view, name="logout"),
    path("accounts/post-login/", views.post_login_redirect, name="post-login-redirect"),
    path("accounts/verify-email/", views.verification_pending, name="verification-pending"),
    path("accounts/verify-email/<uidb64>/<token>/", views.verify_email, name="verify-email"),
    path("accounts/resend-verification/", views.resend_verification, name="resend-verification"),
    path("accounts/password-reset-required/", views.placeholder_view, {"title": "Password reset required"}, name="password-reset-required"),
    path("accounts/email-verification-required/", views.verification_pending, name="email-verification-required"),
    path("accounts/onboarding/photographer/", views.placeholder_view, {"title": "Photographer onboarding"}, name="photographer-onboarding"),
    path("accounts/enable-photographer-workspace/", views.placeholder_view, {"title": "Enable Photographer Workspace"}, name="enable-photographer-workspace"),
    path("accounts/find-photos/", views.placeholder_view, {"title": "Find My Photos"}, name="find-photos-placeholder"),
    path("accounts/marketplace-request/", views.placeholder_view, {"title": "Marketplace Request"}, name="marketplace-request-placeholder"),
    path("accounts/dashboard/client/", views.placeholder_view, {"title": "Client dashboard"}, name="client-dashboard"),
    path("accounts/dashboard/photographer/", views.placeholder_view, {"title": "Photographer dashboard"}, name="photographer-dashboard"),
    path("accounts/dashboard/marketplace/", views.placeholder_view, {"title": "Marketplace"}, name="marketplace-dashboard"),
    path("accounts/dashboard/operations/", views.placeholder_view, {"title": "Operations dashboard"}, name="operations-dashboard"),
]
