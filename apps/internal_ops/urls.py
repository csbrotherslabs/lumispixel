from django.urls import path

from . import views
from .customer_views import customer_detail, customer_list
from .ticket_views import ticket_detail, ticket_list

app_name = "internal_ops"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("customers/", customer_list, name="customers"),
    path("customers/<uuid:user_id>/", customer_detail, name="customer_detail"),
    path("tickets/", ticket_list, name="tickets"),
    path("tickets/<str:reference>/", ticket_detail, name="ticket_detail"),
]
