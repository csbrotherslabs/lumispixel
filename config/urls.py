from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.core.health import live, ready
from apps.core.support_views import help_center, support_attachment_download, support_ticket_detail
from apps.dashboard.client_contracts import client_contracts
from apps.dashboard.workspace_settings import workspace_settings

from apps.photographers.publishing import public_website
from apps.marketplace.verified_reviews import request_booking, submit_review, verify_booking

from apps.notifications.brevo_webhook import brevo_transactional

urlpatterns = [
    path("api/webhooks/brevo/transactional/", brevo_transactional, name="brevo_transactional_webhook"),
    path("p/<slug:slug>/book/verify/<str:token>/", verify_booking, name="public-booking-verify"),
    path("p/<slug:slug>/book/", request_booking, name="public-photographer-booking"),
    path("p/<slug:slug>/reviews/<int:booking_id>/", submit_review, name="public-photographer-review"),
    path("p/<slug:slug>/", public_website, name="public-photographer-website"),
    path("health/live/", live, name="health_live"),
    path("health/ready/", ready, name="health_ready"),
    path("admin/", admin.site.urls),
    path("resources/help-center/", help_center, name="support_help_center"),
    path("resources/help-center/tickets/<str:reference>/", support_ticket_detail, name="support_ticket_detail"),
    path("resources/help-center/tickets/<str:reference>/attachments/<uuid:attachment_id>/download/", support_attachment_download, name="support_attachment_download"),
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
    path("photographer/workspace/clients/<int:pk>/contracts/", client_contracts, name="client_contracts"),
    path("photographer/workspace/", include("apps.dashboard.urls")),
    path("internal/", include("apps.internal_ops.urls")),
    path("api/visual-search/", include("apps.visual_search.urls")),
    path("api/", include("apps.api.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


handler404 = "django.views.defaults.page_not_found"
handler500 = "django.views.defaults.server_error"
