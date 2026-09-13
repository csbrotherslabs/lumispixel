from django.urls import path

from . import views
from .customer_views import customer_detail, customer_list
from .governance_views import approval_create, approval_detail, approval_list, audit_event_detail, audit_export_csv, audit_trail
from .system_views import system_alert_action, system_monitor
from .ticket_views import ticket_detail, ticket_list

app_name = "internal_ops"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("customers/", customer_list, name="customers"),
    path("customers/<uuid:user_id>/", customer_detail, name="customer_detail"),
    path("tickets/", ticket_list, name="tickets"),
    path("tickets/<str:reference>/", ticket_detail, name="ticket_detail"),
    path("approvals/", approval_list, name="approvals"),
    path("approvals/new/", approval_create, name="approval_create"),
    path("approvals/<str:reference>/", approval_detail, name="approval_detail"),
    path("audit/", audit_trail, name="audit"),
    path("audit/export/", audit_export_csv, name="audit_export"),
    path("audit/<int:event_id>/", audit_event_detail, name="audit_detail"),
    path("system/", system_monitor, name="system"),
    path("system/alerts/<int:alert_id>/action/", system_alert_action, name="system_alert_action"),
]
