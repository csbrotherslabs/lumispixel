from django.urls import path
from .api import selfie_search
from .client_permissions import client_selfie_permission
from .private_access_api import (
    issue_private_invitation, revoke_private_invitation, submit_private_request,
    private_request_inbox, review_private_request,
)

app_name = "visual_search"
urlpatterns = [
    path("selfie/", selfie_search, name="selfie"),
    path("selfie/permission/", client_selfie_permission, name="selfie-permission"),
    path("private-access/request/", submit_private_request, name="private-access-request"),
    path("private-access/inbox/", private_request_inbox, name="private-access-inbox"),
    path("private-access/galleries/<int:gallery_id>/invite/", issue_private_invitation, name="private-access-invite"),
    path("private-access/invitations/<int:invitation_id>/revoke/", revoke_private_invitation, name="private-access-revoke"),
    path("private-access/requests/<int:request_id>/review/", review_private_request, name="private-access-review"),
]
