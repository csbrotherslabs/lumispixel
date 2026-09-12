from django.urls import path

from . import account_views, invitation_views, views

app_name = "galleries"

urlpatterns = [
    path("client-galleries/", views.client_galleries, name="client_galleries"),
    path("access/<str:token>/", views.client_gallery_access, name="client_gallery_access"),
    path("access/<str:token>/photos/<int:photo_id>/media/", views.client_gallery_photo_media, name="client_gallery_photo_media"),
    path("access/<str:token>/photos/<int:photo_id>/favorite/", views.client_gallery_favorite, name="client_gallery_favorite"),
    path("access/<str:token>/photos/<int:photo_id>/download/", views.client_gallery_download, name="client_gallery_download"),
    path("my/invitations/<int:invitation_id>/open/", account_views.client_account_gallery_access, name="client_account_gallery_access"),
    path("share-link/<int:gallery_id>/<int:invitation_id>/", views.issue_client_gallery_share_link, name="issue_client_gallery_share_link"),
    path("invite/<int:gallery_id>/", invitation_views.prepare_client_gallery_invitation, name="prepare_client_gallery_invitation"),
    path("invite/<int:gallery_id>/<int:invitation_id>/resend/", invitation_views.resend_client_gallery_invitation, name="resend_client_gallery_invitation"),
]
