from django.urls import path

from . import views

app_name = "galleries"

urlpatterns = [
    path("client-galleries/", views.client_galleries, name="client_galleries"),
]
