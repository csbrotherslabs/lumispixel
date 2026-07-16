from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("post-login/", views.post_login_redirect, name="post-login-redirect"),
    path("password-reset-required/", views.placeholder_view, {"title": "Password reset required"}, name="password-reset-required"),
    path("email-verification-required/", views.placeholder_view, {"title": "Email verification required"}, name="email-verification-required"),
    path("onboarding/photographer/", views.placeholder_view, {"title": "Photographer onboarding"}, name="photographer-onboarding"),
    path("dashboard/client/", views.placeholder_view, {"title": "Client dashboard"}, name="client-dashboard"),
    path("dashboard/photographer/", views.placeholder_view, {"title": "Photographer dashboard"}, name="photographer-dashboard"),
    path("dashboard/marketplace/", views.placeholder_view, {"title": "Marketplace"}, name="marketplace-dashboard"),
    path("dashboard/operations/", views.placeholder_view, {"title": "Operations dashboard"}, name="operations-dashboard"),
]
