from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("pricing/", views.public_page, {"page_key": "pricing"}, name="pricing"),
    path("", views.public_page, {"page_key": "billing"}, name="billing"),
]
