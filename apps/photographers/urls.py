from django.urls import path

from . import views

app_name = "photographers"

urlpatterns = [
    path("onboarding/welcome/", views.onboarding_welcome, name="onboarding-welcome"),
    path("onboarding/profile/", views.onboarding_profile, name="onboarding-profile"),
    path("onboarding/specialties/", views.onboarding_specialties, name="onboarding-specialties"),
    path("onboarding/business/", views.onboarding_business, name="onboarding-business"),
    path("onboarding/theme/", views.onboarding_theme, name="onboarding-theme"),
]
