from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.models import PhotographerProfile
from apps.core.views import add

from .activity import log_gallery_activity
from .analytics import track_gallery_event
from .models import (
    AccessToken,
    Album,
    Gallery,
    GalleryActivity,
    GalleryAnalyticsEvent,
    GalleryInvitation,
    GalleryPermission,
    GalleryPhoto,
    GallerySettings,
)

add("client_galleries", "Client Galleries", "Products", description="Present polished online galleries for delivering, sharing, favoriting, and selling photography.")


def client_galleries(request):
    context = {
        "features": [
            ("Beautiful layouts", "Elegant presentation keeps the focus on each photograph."),
            ("Fast browsing", "Designed for smooth movement through large moments."),
            ("Favorites", "Clients can save selections when enabled by the photographer."),
            ("Private sharing", "Share access with family using photographer-approved settings."),
            ("High-resolution previews", "Present images with a polished, premium viewing feel."),
            ("Photographer branding", "Keep delivery aligned with your studio identity."),
            ("Responsive viewing", "Galleries adapt across desktop, tablet, and mobile."),
        ],
        "journey": ["Photographer Uploads Photos", "Gallery Created", "Client Receives Link", "Browse Photos", "Save Favorites", "Download Available Images", "Order Prints", "Share Memories"],
        "device_points": ["Responsive galleries", "Touch-friendly browsing", "Fast loading", "Consistent experience"],
        "client_needs": ["Favorites", "Slideshows", "Downloads", "Albums", "Collections", "Sharing", "QR Codes", "Password Protection", "Photographer branding"],
        "controls": ["Private galleries", "Password protection", "Download permissions", "Print products", "Gallery expiration", "Branding", "Watermarks", "Event organization"],
        "sharing": ["Private links", "Family sharing", "QR codes", "Favorites collections", "Social sharing where appropriate", "Simple navigation"],
        "occasions": [
            ("Wedding", "bi-heart"), ("Graduation", "bi-mortarboard"), ("Sports", "bi-trophy"), ("School", "bi-book"),
            ("Corporate", "bi-briefcase"), ("Portrait", "bi-person-square"), ("Family", "bi-people"), ("Real Estate", "bi-house"),
            ("Events", "bi-calendar-event"), ("Commercial", "bi-badge-ad"), ("Travel", "bi-airplane"), ("Festivals", "bi-music-note-beamed"),
        ],
        "comparison": [("Email attachments", "Beautiful online gallery"), ("USB drives", "Easy browsing"), ("Multiple folders", "Favorites"), ("Large ZIP files", "Photo search when enabled"), ("Confusing downloads", "Downloads when available"), ("One-time handoff", "Sharing and premium revisit experience")],
        "story_steps": ["Event Completed", "Photographer Curates the Gallery", "Client Receives Their Private Gallery", "Favorite the Best Moments", "Download or Order Keepsakes", "Share with Family and Friends", "Revisit Memories Anytime"],
        "customization": [
            ("Photographer branding", "Display your logo and business identity throughout the gallery."),
            ("Personalized Cover Images", "Create a welcoming first impression with a custom gallery cover."),
            ("Event Organization", "Organize galleries by weddings, sports, portraits, schools, corporate events, and more."),
            ("Flexible Layouts", "Present photos in clean layouts designed for viewing and discovery."),
            ("Client Experience", "Provide intuitive browsing across desktop, tablet, and mobile devices."),
            ("Gallery Controls", "Customize downloads, favorites, sharing, and products based on your workflow."),
        ],
        "faqs": [
            ("Do I need an account?", "Some galleries may require an account, password, private link, or event code depending on photographer settings."),
            ("Can I download photos?", "Downloads are available when enabled by the photographer and depending on gallery settings."),
            ("Can I order prints?", "Print ordering may be available when the photographer offers products for that gallery."),
            ("Can I share my gallery?", "Sharing options depend on the privacy and access settings selected by the photographer."),
            ("Can galleries be password protected?", "LumisPixel is designed to support private and password-protected gallery experiences."),
            ("Can I view galleries on my phone?", "Yes. Galleries are designed for responsive viewing across modern devices."),
            ("Can photographers customize galleries?", "Photographers can shape branding, access, downloads, products, and other options as supported by their workflow."),
            ("How long will galleries remain available?", "Availability depends on the photographer’s gallery settings, expiration choices, and delivery workflow."),
        ],
    }
    return render(request, "client_galleries.html", context)


def _client_gallery_access(raw_token):
    token_hash = AccessToken.digest(raw_token)
    token = (
        AccessToken.objects.select_related("invitation__gallery__photographer")
        .filter(token_hash=token_hash)
        .first()
    )
    if not token or token.revoked_at:
        raise Http404
    now = timezone.now()
    if token.expires_at and token.expires_at <= now:
        raise Http404

    invitation = token.invitation
    gallery = invitation.gallery
    if invitation.status == GalleryInvitation.Status.DISABLED:
        raise Http404
    if gallery.deleted_at or gallery.archived_at:
        raise Http404
    if gallery.status not in {Gallery.Status.PUBLISHED, Gallery.Status.DELIVERED}:
        raise Http404
    if gallery.expires_at and gallery.expires_at <= now:
        raise Http404

    permissions = GalleryPermission.objects.filter(gallery=gallery).first() or GalleryPermission(gallery=gallery)
    settings = GallerySettings.objects.filter(gallery=gallery).first() or GallerySettings(gallery=gallery, gallery_url=gallery.slug)
    if not permissions.view_gallery:
        raise Http404
    return token, invitation, gallery, permissions, settings


def _session_identifier(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key or ""


def _record_client_access(request, token, invitation, gallery):
    now = timezone.now()
    AccessToken.objects.filter(pk=token.pk).update(last_used_at=now)
    GalleryInvitation.objects.filter(pk=invitation.pk).update(
        last_access_at=now,
        status=GalleryInvitation.Status.ACTIVE,
    )
    track_gallery_event(
        gallery=gallery,
        event_type=GalleryAnalyticsEvent.EventType.VIEW,
        visitor_identifier=token.token_hash,
        session_identifier=_session_identifier(request),
        user=request.user,
        source="invite_link",
    )
    log_gallery_activity(
        gallery=gallery,
        event_type=GalleryActivity.EventType.CLIENT_VIEWED,
        actor=request.user,
        actor_type=GalleryActivity.ActorType.CLIENT,
        related_object=invitation,
    )


@require_GET
def client_gallery_access(request, token):
    token_record, invitation, gallery, permissions, settings = _client_gallery_access(token)
    _record_client_access(request, token_record, invitation, gallery)

    photos = list(
        GalleryPhoto.objects.filter(
            gallery=gallery,
            is_visible=True,
            status=GalleryPhoto.Status.COMPLETED,
        ).order_by("created_at", "pk")
    )
    albums = list(
        Album.objects.filter(gallery=gallery)
        .exclude(visibility=Album.Visibility.HIDDEN)
        .order_by("display_order", "pk")
    )
    favorite_ids = set(
        GalleryAnalyticsEvent.objects.filter(
            gallery=gallery,
            visitor_identifier=token_record.token_hash,
            event_type=GalleryAnalyticsEvent.EventType.FAVORITE,
            related_photo__isnull=False,
        ).values_list("related_photo_id", flat=True)
    )
    for photo in photos:
        photo.is_client_favorite = photo.pk in favorite_ids

    return render(
        request,
        "galleries/client_gallery.html",
        {
            "gallery": gallery,
            "invitation": invitation,
            "photos": photos,
            "albums": albums,
            "permissions": permissions,
            "gallery_settings": settings,
            "access_token": token,
            "can_favorite": permissions.favorite_photos and settings.enable_favorites,
            "can_download": permissions.download_images and settings.allow_downloads,
        },
    )


@require_GET
def client_gallery_photo_media(request, token, photo_id):
    _, _, gallery, _, _ = _client_gallery_access(token)
    photo = get_object_or_404(
        GalleryPhoto,
        pk=photo_id,
        gallery=gallery,
        is_visible=True,
        status=GalleryPhoto.Status.COMPLETED,
    )
    track_gallery_event(
        gallery=gallery,
        event_type=GalleryAnalyticsEvent.EventType.PHOTO_VIEW,
        visitor_identifier=AccessToken.digest(token),
        session_identifier=_session_identifier(request),
        user=request.user,
        photo=photo,
        source="invite_link",
    )
    return FileResponse(photo.file.open("rb"), as_attachment=False, filename=photo.original_name)


@require_POST
def client_gallery_favorite(request, token, photo_id):
    token_record, _, gallery, permissions, settings = _client_gallery_access(token)
    if not (permissions.favorite_photos and settings.enable_favorites):
        return HttpResponseForbidden()
    photo = get_object_or_404(
        GalleryPhoto,
        pk=photo_id,
        gallery=gallery,
        is_visible=True,
        status=GalleryPhoto.Status.COMPLETED,
    )
    already_favorited = GalleryAnalyticsEvent.objects.filter(
        gallery=gallery,
        visitor_identifier=token_record.token_hash,
        event_type=GalleryAnalyticsEvent.EventType.FAVORITE,
        related_photo=photo,
    ).exists()
    if not already_favorited:
        track_gallery_event(
            gallery=gallery,
            event_type=GalleryAnalyticsEvent.EventType.FAVORITE,
            visitor_identifier=token_record.token_hash,
            session_identifier=_session_identifier(request),
            user=request.user,
            photo=photo,
            source="invite_link",
        )
        Gallery.objects.filter(pk=gallery.pk).update(favorite_count=F("favorite_count") + 1)
        log_gallery_activity(
            gallery=gallery,
            event_type=GalleryActivity.EventType.CLIENT_FAVORITED,
            actor=request.user,
            actor_type=GalleryActivity.ActorType.CLIENT,
            related_object=photo,
        )
    return render(
        request,
        "galleries/favorite_result.html",
        {"gallery": gallery, "photo": photo, "access_token": token, "favorited": True},
    )


@require_GET
def client_gallery_download(request, token, photo_id):
    token_record, _, gallery, permissions, settings = _client_gallery_access(token)
    now = timezone.now()
    if not (permissions.download_images and settings.allow_downloads):
        return HttpResponseForbidden()
    if permissions.download_expires_at and permissions.download_expires_at <= now:
        return HttpResponseForbidden()

    photo = get_object_or_404(
        GalleryPhoto,
        pk=photo_id,
        gallery=gallery,
        is_visible=True,
        status=GalleryPhoto.Status.COMPLETED,
    )
    if settings.download_limit is not None:
        used = GalleryAnalyticsEvent.objects.filter(
            gallery=gallery,
            visitor_identifier=token_record.token_hash,
            event_type=GalleryAnalyticsEvent.EventType.DOWNLOAD,
        ).count()
        if used >= settings.download_limit:
            return HttpResponseForbidden()

    track_gallery_event(
        gallery=gallery,
        event_type=GalleryAnalyticsEvent.EventType.DOWNLOAD,
        visitor_identifier=token_record.token_hash,
        session_identifier=_session_identifier(request),
        user=request.user,
        photo=photo,
        source="invite_link",
    )
    Gallery.objects.filter(pk=gallery.pk).update(download_count=F("download_count") + 1)
    log_gallery_activity(
        gallery=gallery,
        event_type=GalleryActivity.EventType.PHOTO_DOWNLOADED,
        actor=request.user,
        actor_type=GalleryActivity.ActorType.CLIENT,
        related_object=photo,
    )
    return FileResponse(photo.file.open("rb"), as_attachment=True, filename=photo.original_name)


@login_required
@require_POST
def issue_client_gallery_share_link(request, gallery_id, invitation_id):
    profile = PhotographerProfile.objects.filter(user=request.user).first()
    if not profile:
        raise Http404
    invitation = get_object_or_404(
        GalleryInvitation.objects.select_related("gallery"),
        pk=invitation_id,
        gallery_id=gallery_id,
        gallery__photographer=profile,
    )
    gallery = invitation.gallery
    if gallery.status not in {Gallery.Status.PUBLISHED, Gallery.Status.DELIVERED}:
        return HttpResponseForbidden("Publish the gallery before creating a client link.")
    if invitation.status == GalleryInvitation.Status.DISABLED:
        return HttpResponseForbidden("This invitation is disabled.")

    invitation.access_tokens.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
    _, raw_token = AccessToken.issue(invitation, expires_at=gallery.expires_at)
    share_url = request.build_absolute_uri(reverse("galleries:client_gallery_access", args=[raw_token]))
    log_gallery_activity(
        gallery=gallery,
        event_type=GalleryActivity.EventType.GALLERY_SHARED,
        actor=request.user,
        related_object=invitation,
    )
    return render(
        request,
        "galleries/share_link_ready.html",
        {"gallery": gallery, "invitation": invitation, "share_url": share_url},
    )
