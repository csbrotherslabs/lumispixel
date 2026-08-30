from django.urls import path

from . import views

app_name = "photographers"

urlpatterns = [
    path("setup-dashboard/", views.setup_dashboard, name="setup-dashboard"),
    path("setup-dashboard/", views.setup_dashboard, name="photographer_setup_dashboard"),
    path("onboarding/skip/", views.skip_onboarding, name="onboarding-skip"),
    path("onboarding/welcome/", views.onboarding_welcome, name="onboarding-welcome"),
    path("onboarding/profile/", views.onboarding_profile, name="onboarding-profile"),
    path("onboarding/specialties/", views.onboarding_specialties, name="onboarding-specialties"),
    path("onboarding/business/", views.onboarding_business, name="onboarding-business"),
    path("onboarding/theme/", views.onboarding_theme, name="onboarding-theme"),
    path("website/builder/", views.onboarding_theme, name="website-builder"),
    path("onboarding/theme-preview/selection/", views.selected_theme_preview, name="selected-theme-preview"),
    path("onboarding/theme-preview/<slug:theme_slug>/", views.theme_preview, name="theme-preview"),
    path("onboarding/theme-preview/basic/", views.theme_preview, {"theme_slug": "basic"}, name="photographer_onboarding_theme_preview_basic"),
    path("onboarding/theme-preview/elegant/", views.theme_preview, {"theme_slug": "elegant"}, name="photographer_onboarding_theme_preview_elegant"),
    path("onboarding/theme-preview/modern-studio/", views.theme_preview, {"theme_slug": "modern-studio"}, name="photographer_onboarding_theme_preview_modern_studio"),
    path("onboarding/theme-preview/cinematic/", views.theme_preview, {"theme_slug": "cinematic"}, name="photographer_onboarding_theme_preview_cinematic"),
    path("onboarding/theme-preview/portfolio-editorial/", views.theme_preview, {"theme_slug": "portfolio-editorial"}, name="photographer_onboarding_theme_preview_portfolio_editorial"),
    path("onboarding/theme-preview/sports-events/", views.theme_preview, {"theme_slug": "sports-events"}, name="photographer_onboarding_theme_preview_sports_events"),
]

from . import public_views

urlpatterns += [
    path("websites/", public_views.public_page, {"page_key": "photographer_websites"}, name="websites"),
]
