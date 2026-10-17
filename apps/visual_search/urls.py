from django.urls import path
from .api import selfie_search

app_name = "visual_search"
urlpatterns = [
    path("selfie/", selfie_search, name="selfie"),
]
