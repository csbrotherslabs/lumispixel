from django.urls import path
from .api import selfie_search
from .client_permissions import client_selfie_permission, client_selfie_permission_page, client_biometric_deletion\nfrom .face_deletion_api import photographer_face_deletion_inbox, photographer_confirm_face_deletion
from .private_access_api import (
    issue_private_invitation, revoke_private_invitation, submit_private_request,
    private_request_inbox, review_private_request,
)

app_name = "visual_search"
urlpatterns = [
    path("selfie/", selfie_search, name="selfie"),
    path("selfie/permission/", client_selfie_permission, name="selfie-permission"),
    path("selfie/privacy/", client_selfie_permission_page, name="selfie-privacy"),
    path("selfie/deletion/", client_biometric_deletion, name="selfie-deletion"),\n    path("selfie/deletion/photographer/inbox/", photographer_face_deletion_inbox, name="face-deletion-inbox"),\n    path("selfie/deletion/photographer/<int:deletion_id>/confirm/", photographer_confirm_face_deletion, name="face-deletion-confirm"),
    path("private-access/request/", submit_private_request, name="private-access-request"),
    path("private-access/inbox/", private_request_inbox, name="private-access-inbox"),
    path("private-access/galleries/<int:gallery_id>/invite/", issue_private_invitation, name="private-access-invite"),
    path("private-access/invitations/<int:invitation_id>/revoke/", revoke_private_invitation, name="private-access-revoke"),
    path("private-access/requests/<int:request_id>/review/", review_private_request, name="private-access-review"),
]
