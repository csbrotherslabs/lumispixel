from django.urls import path

from . import views

app_name = "ai_engine"

urlpatterns = [
    path("photo-search/", views.ai_photo_search, name="photo_search"),
    path("editing-culling/", views.editing_culling, name="editing_culling"),
]
