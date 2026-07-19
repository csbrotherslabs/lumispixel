from django.urls import path

from . import views

app_name = "galleries"

urlpatterns = [
    path("client-galleries/", views.public_page, {"page_key": "client_galleries"}, name="client_galleries"),
]
