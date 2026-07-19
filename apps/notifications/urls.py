from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.public_page, {"page_key": "notifications"}, name="index"),
]
