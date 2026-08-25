from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.index, name="index"),
    path("<int:pk>/read/", views.mark_read, name="mark-read"),
    path("<int:pk>/dismiss/", views.dismiss, name="dismiss"),
    path("read-all/", views.mark_all_read, name="mark-all-read"),
]
