from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    path("photographer/", include("apps.photographers.urls")),
    path("client/", include("apps.clients.urls")),
    path("galleries/", include("apps.galleries.urls")),
    path("broker/", include("apps.broker.urls")),
    path("marketplace/", include("apps.marketplace.urls")),
    path("billing/", include("apps.billing.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("api/", include("apps.api.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


handler404 = "django.views.defaults.page_not_found"
handler500 = "django.views.defaults.server_error"
