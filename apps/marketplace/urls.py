from django.urls import path

from . import views

app_name = "marketplace"

urlpatterns = [
    path("find-a-photographer/", views.public_page, {"page_key": "find_photographer"}, name="find_photographer"),
    path("", views.public_page, {"page_key": "marketplace"}, name="marketplace"),
]
