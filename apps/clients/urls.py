from django.urls import path

from . import views

app_name = "clients"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("settings/", views.account_settings, name="account-settings"),
    path("setup-dashboard/", views.setup_dashboard, name="setup-dashboard"),
    path("setup-dashboard/", views.setup_dashboard, name="client_setup_dashboard"),
    path("onboarding/skip/", views.skip_onboarding, name="onboarding-skip"),
    path("onboarding/welcome/", views.onboarding_welcome, name="onboarding-welcome"),
    path("onboarding/profile/", views.onboarding_profile, name="onboarding-profile"),
    path(
        "onboarding/how-it-works/",
        views.onboarding_how_it_works,
        name="onboarding-how-it-works",
    ),
]

from . import public_views

urlpatterns += [
    path("for-clients/", public_views.for_clients, name="for_clients"),
    path("contracts/review/<str:token>/", public_views.contract_review, name="contract-review"),
    path("contracts/review/<str:token>/signed-pdf/", public_views.signed_contract_pdf,
         name="signed-contract-pdf"),
    path("contracts/review/<str:token>/signed-pdf/download/", public_views.signed_contract_pdf,
         {"disposition": "attachment"}, name="signed-contract-pdf-download"),
]
