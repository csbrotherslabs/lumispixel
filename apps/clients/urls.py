from django.urls import path

from . import views

app_name = "clients"

urlpatterns = [
    path("onboarding/welcome/", views.onboarding_welcome, name="onboarding-welcome"),
    path("onboarding/profile/", views.onboarding_profile, name="onboarding-profile"),
    path("onboarding/how-it-works/", views.onboarding_how_it_works, name="onboarding-how-it-works"),
]
