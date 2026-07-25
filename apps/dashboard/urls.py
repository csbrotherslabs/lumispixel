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
    path("crm/", views.module_placeholder, {"module_key": "crm"}, name="crm"),
    path("leads/", views.module_placeholder, {"module_key": "leads"}, name="leads"),
    path("ai-search/", views.module_placeholder, {"module_key": "ai_search"}, name="ai_search"),
    path("albums/", views.module_placeholder, {"module_key": "albums"}, name="albums"),
    path("calendar/", views.module_placeholder, {"module_key": "calendar"}, name="calendar"),
    path("bookings/", views.module_placeholder, {"module_key": "bookings"}, name="bookings"),
    path("contracts/", views.module_placeholder, {"module_key": "contracts"}, name="contracts"),
    path("invoices/", views.module_placeholder, {"module_key": "invoices"}, name="invoices"),
    path("payments/", views.module_placeholder, {"module_key": "payments"}, name="payments"),
    path("revenue/", views.module_placeholder, {"module_key": "revenue"}, name="revenue"),
    path("reviews/", views.module_placeholder, {"module_key": "reviews"}, name="reviews"),
    path("referrals/", views.module_placeholder, {"module_key": "referrals"}, name="referrals"),
    path("workflows/", views.module_placeholder, {"module_key": "workflows"}, name="workflows"),
    path("ai-assistant/", views.module_placeholder, {"module_key": "ai_assistant"}, name="ai_assistant"),
    path("team/", views.module_placeholder, {"module_key": "team"}, name="team"),
    path("equipment/", views.module_placeholder, {"module_key": "equipment"}, name="equipment"),
    path("tasks/", views.module_placeholder, {"module_key": "tasks"}, name="tasks"),
    path("notifications/", views.module_placeholder, {"module_key": "notifications"}, name="notifications"),
    path("help/", views.module_placeholder, {"module_key": "help"}, name="help"),
]
