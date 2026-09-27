from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    path("locations/regions/", views.administrative_regions, name="administrative-regions"),
    path("coming-soon/", views.public_page, {"page_key": "api_coming_soon"}, name="api_coming_soon"),
    path("developer-center/", views.public_page, {"page_key": "developer_center"}, name="developer_center"),
]
