from django.urls import path

from . import views

app_name = "clients"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("setup-dashboard/", views.setup_dashboard, name="setup-dashboard"),
    path("setup-dashboard/", views.setup_dashboard, name="client_setup_dashboard"),
    path("onboarding/skip/", views.skip_onboarding, name="onboarding-skip"),
    path("onboarding/welcome/", views.onboarding_welcome, name="onboarding-welcome"),
    path("onboarding/profile/", views.onboarding_profile, name="onboarding-profile"),
    path("onboarding/how-it-works/", views.onboarding_how_it_works, name="onboarding-how-it-works"),
]
