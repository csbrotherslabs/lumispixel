from django.urls import path

from . import views
from .customer_views import customer_detail, customer_list

app_name = "internal_ops"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("customers/", customer_list, name="customers"),
    path("customers/<uuid:user_id>/", customer_detail, name="customer_detail"),
]
