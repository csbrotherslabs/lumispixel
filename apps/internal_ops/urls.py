from django.urls import path

from . import views

app_name = "internal_ops"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
]
