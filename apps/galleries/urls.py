from django.urls import path

from . import account_views, invitation_views, views

app_name = "galleries"

urlpatterns = [
    path("g/<uuid:public_id>/", views.stable_gallery_access, name="stable_gallery_access"),
    path("client-galleries/", views.client_galleries, name="client_galleries"),
    path("access/<str:token>/", views.client_gallery_access, name="client_gallery_access"),
    path("access/<str:token>/photos/<int:photo_id>/media/", views.client_gallery_photo_media, name="client_gallery_photo_media"),
    path("access/<str:token>/photos/<int:photo_id>/favorite/", views.client_gallery_favorite, name="client_gallery_favorite"),
    path("access/<str:token>/photos/<int:photo_id>/comment/", views.client_gallery_comment, name="client_gallery_comment"),
    path("access/<str:token>/photos/<int:photo_id>/download/", views.client_gallery_download, name="client_gallery_download"),
    path("access/<str:token>/photos/<int:photo_id>/download-original/", views.client_gallery_download_original, name="client_gallery_download_original"),
    path("access/<str:token>/download/", views.client_gallery_download_all, name="client_gallery_download_all"),
    path("access/<str:token>/share/", views.client_gallery_share, name="client_gallery_share"),
    path("access/<str:token>/prints/", views.client_gallery_print_store, name="client_gallery_print_store"),
    path("my/invitations/<int:invitation_id>/open/", account_views.client_account_gallery_access, name="client_account_gallery_access"),
    path("share-link/<int:gallery_id>/<int:invitation_id>/", views.issue_client_gallery_share_link, name="issue_client_gallery_share_link"),
    path("invite/<int:gallery_id>/", invitation_views.prepare_client_gallery_invitation, name="prepare_client_gallery_invitation"),
    path("invite/<int:gallery_id>/<int:invitation_id>/resend/", invitation_views.resend_client_gallery_invitation, name="resend_client_gallery_invitation"),
]
