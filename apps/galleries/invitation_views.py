from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import PhotographerProfile

from .activity import log_gallery_activity
from .models import AccessToken, Gallery, GalleryActivity, GalleryInvitation
from .services import GalleryInvitationDeliveryError, send_gallery_invitation_email


def _client_access_url(gallery):
    return f"{reverse('photographer_workspace:gallery_workspace', args=[gallery.pk])}?tab=client-access#invite-client"


def _owned_gallery(request, gallery_id):
    profile = PhotographerProfile.objects.filter(user=request.user).first()
    if not profile:
        raise Http404
    return get_object_or_404(Gallery, pk=gallery_id, photographer=profile)


def _issue_and_email(request, invitation):
    """Issue a replacement token without invalidating the current link unless delivery succeeds."""
    gallery = invitation.gallery
    token_record, raw_token = AccessToken.issue(invitation, expires_at=gallery.expires_at)
    try:
        gallery_url = send_gallery_invitation_email(
            request,
            invitation=invitation,
            raw_token=raw_token,
        )
    except GalleryInvitationDeliveryError:
        token_record.revoked_at = timezone.now()
        token_record.save(update_fields=["revoked_at"])
        raise

    invitation.access_tokens.filter(revoked_at__isnull=True).exclude(pk=token_record.pk).update(
        revoked_at=timezone.now()
    )
    return token_record, gallery_url


@login_required
@require_POST
def prepare_client_gallery_invitation(request, gallery_id):
    gallery = _owned_gallery(request, gallery_id)
    redirect_url = _client_access_url(gallery)
    if gallery.status not in {Gallery.Status.PUBLISHED, Gallery.Status.DELIVERED}:
        messages.error(request, "Publish the gallery before sending a client invitation.")
        return redirect(redirect_url)

    name = request.POST.get("client_name", "").strip()
    email = request.POST.get("email", "").strip().lower()
    if not name or not email:
        messages.error(request, "Enter a client name and email address.")
        return redirect(redirect_url)

    invitation, created = GalleryInvitation.objects.get_or_create(
        gallery=gallery,
        email=email,
        defaults={"client_name": name},
    )
    if not created:
        invitation.client_name = name
        invitation.status = GalleryInvitation.Status.PENDING
        invitation.save(update_fields=["client_name", "status"])

    try:
        _issue_and_email(request, invitation)
    except GalleryInvitationDeliveryError:
        messages.error(
            request,
            "The invitation was prepared, but the email could not be sent. Please try again.",
        )
        return redirect(redirect_url)

    if not created:
        invitation.resent_at = timezone.now()
        invitation.save(update_fields=["resent_at"])
    log_gallery_activity(
        gallery=gallery,
        event_type=GalleryActivity.EventType.CLIENT_INVITED,
        description=f"A secure gallery invitation was emailed to {name}.",
        actor=request.user,
        related_object=invitation,
        metadata={"client": name, "delivery": "email"},
    )
    messages.success(request, f"Gallery invitation sent to {email}.")
    return redirect(redirect_url)


@login_required
@require_POST
def resend_client_gallery_invitation(request, gallery_id, invitation_id):
    gallery = _owned_gallery(request, gallery_id)
    redirect_url = _client_access_url(gallery)
    invitation = get_object_or_404(GalleryInvitation, pk=invitation_id, gallery=gallery)

    if gallery.status not in {Gallery.Status.PUBLISHED, Gallery.Status.DELIVERED}:
        messages.error(request, "Publish the gallery before resending a client invitation.")
        return redirect(redirect_url)
    if invitation.status == GalleryInvitation.Status.DISABLED:
        messages.error(request, "Enable this invitation before resending it.")
        return redirect(redirect_url)

    try:
        _issue_and_email(request, invitation)
    except GalleryInvitationDeliveryError:
        messages.error(request, "The invitation email could not be resent. The previous secure link is still valid.")
        return redirect(redirect_url)

    invitation.status = GalleryInvitation.Status.PENDING
    invitation.resent_at = timezone.now()
    invitation.save(update_fields=["status", "resent_at"])
    log_gallery_activity(
        gallery=gallery,
        event_type=GalleryActivity.EventType.CLIENT_INVITED,
        description=f"A fresh secure gallery invitation was emailed to {invitation.client_name}.",
        actor=request.user,
        related_object=invitation,
        metadata={"client": invitation.client_name, "delivery": "email", "resent": True},
    )
    messages.success(request, f"Gallery invitation resent to {invitation.email}.")
    return redirect(redirect_url)
