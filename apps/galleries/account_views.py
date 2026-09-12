from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import AccessToken, Gallery, GalleryInvitation, GalleryPermission


def available_invitations_for_user(user):
    """Return active gallery invitations that belong to a verified account email."""
    if not user.is_authenticated or not user.email_verified or not user.email:
        return GalleryInvitation.objects.none()

    now = timezone.now()
    return (
        GalleryInvitation.objects.select_related("gallery", "gallery__photographer", "gallery__photographer__user")
        .filter(
            email__iexact=user.email,
            status__in=[GalleryInvitation.Status.PENDING, GalleryInvitation.Status.ACTIVE],
            gallery__status__in=[Gallery.Status.PUBLISHED, Gallery.Status.DELIVERED],
            gallery__archived_at__isnull=True,
            gallery__deleted_at__isnull=True,
        )
        .filter(Q(gallery__expires_at__isnull=True) | Q(gallery__expires_at__gt=now))
        .order_by("-invited_at")
    )


@login_required
@require_GET
def client_account_gallery_access(request, invitation_id):
    """Convert verified account ownership of an invited email into a fresh gallery session link."""
    if not request.user.email_verified:
        raise PermissionDenied("Verify your email address before opening invited galleries.")

    invitation = get_object_or_404(
        available_invitations_for_user(request.user),
        pk=invitation_id,
    )
    gallery = invitation.gallery
    permissions = GalleryPermission.objects.filter(gallery=gallery).first()
    if permissions is not None and not permissions.view_gallery:
        raise Http404

    _, raw_token = AccessToken.issue(invitation, expires_at=gallery.expires_at)
    return redirect("galleries:client_gallery_access", token=raw_token)
