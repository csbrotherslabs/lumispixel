from django.urls import path
from .api import selfie_search
from .private_access_api import (
    issue_private_invitation, submit_private_request, review_private_request,
)

app_name = "visual_search"
urlpatterns = [
    path("selfie/", selfie_search, name="selfie"),
    path("private-access/request/", submit_private_request, name="private-access-request"),
    path("private-access/galleries/<int:gallery_id>/invite/", issue_private_invitation, name="private-access-invite"),
    path("private-access/requests/<int:request_id>/review/", review_private_request, name="private-access-review"),
]
