from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.core.support_views import help_center, support_ticket_detail
from apps.dashboard.workspace_settings import workspace_settings

urlpatterns = [
    path("admin/", admin.site.urls),
    path("resources/help-center/", help_center, name="support_help_center"),
    path("resources/help-center/tickets/<str:reference>/", support_ticket_detail, name="support_ticket_detail"),
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    path("photographer/", include("apps.photographers.urls")),
    path("client/", include("apps.clients.urls")),
    path("galleries/", include("apps.galleries.urls")),
    path("broker/", include("apps.broker.urls")),
    path("ai/", include("apps.ai_engine.urls")),
    path("marketplace/", include("apps.marketplace.urls")),
    path("billing/", include("apps.billing.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("photographer/workspace/settings/", workspace_settings),
    path("photographer/workspace/", include("apps.dashboard.urls")),
    path("internal/", include("apps.internal_ops.urls")),
    path("api/", include("apps.api.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


handler404 = "django.views.defaults.page_not_found"
handler500 = "django.views.defaults.server_error"
