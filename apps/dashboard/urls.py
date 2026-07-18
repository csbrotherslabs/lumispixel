from django.urls import path

from . import views

app_name = "photographer_workspace"

urlpatterns = [
    path("", views.photographer_dashboard, name="dashboard"),
    path("galleries/", views.module_placeholder, {"module_key": "galleries"}, name="galleries"),
    path("clients/", views.module_placeholder, {"module_key": "clients"}, name="clients"),
    path("events/", views.module_placeholder, {"module_key": "events"}, name="events"),
    path("ai/", views.module_placeholder, {"module_key": "ai"}, name="ai"),
    path("website/", views.module_placeholder, {"module_key": "website"}, name="website"),
    path("marketplace/", views.module_placeholder, {"module_key": "marketplace"}, name="marketplace"),
    path("orders/", views.module_placeholder, {"module_key": "orders"}, name="orders"),
    path("billing/", views.module_placeholder, {"module_key": "billing"}, name="billing"),
    path("analytics/", views.module_placeholder, {"module_key": "analytics"}, name="analytics"),
    path("marketing/", views.module_placeholder, {"module_key": "marketing"}, name="marketing"),
    path("profile/", views.module_placeholder, {"module_key": "profile"}, name="profile"),
    path("settings/", views.module_placeholder, {"module_key": "settings"}, name="settings"),
]
