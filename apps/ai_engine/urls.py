from django.urls import path

from . import views

app_name = "ai_engine"

urlpatterns = [
    path("photo-search/", views.public_page, {"page_key": "ai_photo_search"}, name="photo_search"),
    path("editing-culling/", views.public_page, {"page_key": "ai_editing_culling"}, name="editing_culling"),
]
