from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, F
import tempfile
import zipfile
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
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
    AlbumPhoto,
    Gallery,
    GalleryActivity,
    GalleryAnalyticsEvent,
    GalleryInvitation,
    GalleryPermission,
    GalleryPhoto,
    GalleryPhotoComment,
    GallerySettings,
    GalleryStore,
    StoreProduct,
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



def _client_gallery_template(gallery):
    """Resolve presentation independently from gallery content and permissions."""
    templates = {
        Gallery.DesignTemplate.KIMONO_STANDARD_FILTERABLE: "galleries/designs/standard_filterable.html",
        Gallery.DesignTemplate.KIMONO_STORY: "galleries/designs/story.html",
        Gallery.DesignTemplate.KIMONO_MASONRY: "galleries/designs/masonry.html",
        Gallery.DesignTemplate.CINEMATIC: "galleries/designs/cinematic.html",
    }
    return templates.get(gallery.design_template, "galleries/client_gallery.html")


CLIENT_GALLERY_PAGE_SIZE = 60


def _paginate_client_gallery_photos(request, gallery):
    queryset = GalleryPhoto.objects.filter(
        gallery=gallery,
        is_visible=True,
        status=GalleryPhoto.Status.COMPLETED,
    ).order_by("created_at", "pk")
    page = Paginator(queryset, CLIENT_GALLERY_PAGE_SIZE).get_page(request.GET.get("page"))
    return page, list(page.object_list)


def _prepare_client_gallery_content(gallery, photos, albums):
    """Attach presentation-only metadata without changing persisted gallery data."""
    photo_ids = {photo.pk for photo in photos}
    categories = {photo_id: [] for photo_id in photo_ids}
    memberships = (
        AlbumPhoto.objects.filter(album__in=albums, photo_id__in=photo_ids)
        .select_related("album")
        .order_by("album__display_order", "position", "pk")
    )
    for membership in memberships:
        categories.setdefault(membership.photo_id, []).append(f"album-{membership.album_id}")
    for photo in photos:
        photo.client_filter_categories = " ".join(categories.get(photo.pk, []))
    # Cinematic consumes the same prepared content, but needs lightweight
    # chapter metadata so albums can become the horizontal film-strip rail.
    album_photo_ids = {}
    for membership in memberships:
        album_photo_ids.setdefault(membership.album_id, []).append(membership.photo_id)
    photos_by_id = {photo.pk: photo for photo in photos}
    for album in albums:
        chapter_photos = [photos_by_id[photo_id] for photo_id in album_photo_ids.get(album.pk, []) if photo_id in photos_by_id]
        album.client_photo_count = len(chapter_photos)
        album.client_cover_url = ""
        if album.cover_photo_id and album.cover_photo_id in photos_by_id:
            album.client_cover_url = photos_by_id[album.cover_photo_id].delivery_url
        elif chapter_photos:
            album.client_cover_url = chapter_photos[0].delivery_url
    return photos, albums


def _client_gallery_brand(gallery):
    photographer = gallery.photographer
    return photographer.business_name or photographer.display_name or str(photographer)


@require_GET
def stable_gallery_access(request, public_id):
    gallery = get_object_or_404(Gallery.objects.select_related("photographer"), public_id=public_id, archived_at__isnull=True, deleted_at__isnull=True, status__in=[Gallery.Status.PUBLISHED, Gallery.Status.DELIVERED])
    now = timezone.now()
    permissions = GalleryPermission.objects.filter(gallery=gallery).first() or GalleryPermission(gallery=gallery)
    if gallery.expires_at and gallery.expires_at <= now:
        # Automatic lock makes gallery expiration an access-control boundary.
        # Without it, the date remains informational/scheduling metadata.
        if permissions.automatic_gallery_lock:
            raise Http404
    settings = GallerySettings.objects.filter(gallery=gallery).first() or GallerySettings(gallery=gallery, gallery_url=gallery.slug)
    if not permissions.view_gallery:
        raise Http404
    if request.user.is_authenticated and getattr(request.user, "email_verified", False) and request.user.email:
        invitation = GalleryInvitation.objects.filter(gallery=gallery, email__iexact=request.user.email, status__in=[GalleryInvitation.Status.PENDING, GalleryInvitation.Status.ACTIVE]).first()
        if invitation:
            _, raw_token = AccessToken.issue(invitation, expires_at=gallery.expires_at)
            return redirect("galleries:client_gallery_access", token=raw_token)
    if gallery.visibility != Gallery.Visibility.PUBLIC:
        return render(request, "galleries/stable_gallery_gate.html", {"gallery": gallery})
    photo_page, photos = _paginate_client_gallery_photos(request, gallery)
    albums = list(Album.objects.filter(gallery=gallery).exclude(visibility=Album.Visibility.HIDDEN).order_by("display_order", "pk"))
    photos, albums = _prepare_client_gallery_content(gallery, photos, albums)
    return render(request, _client_gallery_template(gallery), {"gallery": gallery, "invitation": None, "photos": photos, "photo_page": photo_page, "albums": albums, "permissions": permissions, "gallery_settings": settings, "access_token": None, "can_favorite": False, "can_download": False, "can_download_gallery": False, "can_download_originals": False, "can_comment": False, "can_purchase_prints": False, "stable_gallery_url": request.build_absolute_uri(), "can_share_gallery": permissions.share_gallery, "gallery_brand": _client_gallery_brand(gallery)})

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
    permissions = GalleryPermission.objects.filter(gallery=gallery).first() or GalleryPermission(gallery=gallery)
    if gallery.expires_at and gallery.expires_at <= now and permissions.automatic_gallery_lock:
        raise Http404

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

    photo_page, photos = _paginate_client_gallery_photos(request, gallery)
    albums = list(
        Album.objects.filter(gallery=gallery)
        .exclude(visibility=Album.Visibility.HIDDEN)
        .order_by("display_order", "pk")
    )
    photos, albums = _prepare_client_gallery_content(gallery, photos, albums)
    favorite_ids = set(
        GalleryAnalyticsEvent.objects.filter(
            gallery=gallery,
            visitor_identifier=token_record.token_hash,
            event_type=GalleryAnalyticsEvent.EventType.FAVORITE,
            related_photo__isnull=False,
        ).values_list("related_photo_id", flat=True)
    )
    comments_by_photo = {}
    if permissions.comment:
        for comment in GalleryPhotoComment.objects.filter(
            gallery=gallery,
            photo__in=photos,
        ).select_related("invitation"):
            comments_by_photo.setdefault(comment.photo_id, []).append(comment)

    interaction_counts = {}
    for row in (
        GalleryAnalyticsEvent.objects.filter(
            gallery=gallery,
            related_photo__in=photos,
            event_type__in=[
                GalleryAnalyticsEvent.EventType.FAVORITE,
                GalleryAnalyticsEvent.EventType.DOWNLOAD,
            ],
        )
        .values("related_photo_id", "event_type")
        .annotate(total=Count("id"))
    ):
        interaction_counts.setdefault(row["related_photo_id"], {})[row["event_type"]] = row["total"]

    for photo in photos:
        photo.is_client_favorite = photo.pk in favorite_ids
        photo.client_comment_list = comments_by_photo.get(photo.pk, [])
        counts = interaction_counts.get(photo.pk, {})
        photo.client_favorite_count = counts.get(GalleryAnalyticsEvent.EventType.FAVORITE, 0)
        photo.client_download_count = counts.get(GalleryAnalyticsEvent.EventType.DOWNLOAD, 0)

    store = GalleryStore.objects.filter(
        gallery=gallery,
        enabled=True,
    ).filter(expires_at__isnull=True).first()
    if not store:
        store = GalleryStore.objects.filter(
            gallery=gallery,
            enabled=True,
            expires_at__gt=timezone.now(),
        ).first()
    print_products = []
    if permissions.purchase_prints and store:
        print_products = list(
            StoreProduct.objects.filter(
                store=store,
                gallery=gallery,
                active=True,
                product_type__in=[
                    StoreProduct.ProductType.PRINT,
                    StoreProduct.ProductType.CANVAS,
                    StoreProduct.ProductType.FRAMED,
                    StoreProduct.ProductType.ALBUM,
                ],
            ).prefetch_related("variants")
        )

    downloads_active = permissions.download_images and (
        not permissions.download_expires_at or permissions.download_expires_at > timezone.now()
    )
    used_downloads = GalleryAnalyticsEvent.objects.filter(
        gallery=gallery,
        visitor_identifier=token_record.token_hash,
        event_type=GalleryAnalyticsEvent.EventType.DOWNLOAD,
    ).count()
    remaining_downloads = None if settings.download_limit is None else max(settings.download_limit - used_downloads, 0)
    can_download = downloads_active and (remaining_downloads is None or remaining_downloads > 0)
    can_download_gallery = can_download and (remaining_downloads is None or remaining_downloads >= photo_page.paginator.count)

    return render(
        request,
        _client_gallery_template(gallery),
        {
            "gallery": gallery,
            "invitation": invitation,
            "photos": photos,
            "photo_page": photo_page,
            "albums": albums,
            "permissions": permissions,
            "gallery_settings": settings,
            "access_token": token,
            "can_favorite": permissions.favorite_photos,
            "can_download": can_download,
            "can_download_gallery": can_download_gallery,
            "remaining_downloads": remaining_downloads,
            "can_download_originals": can_download and permissions.download_originals,
            "can_comment": permissions.comment,
            "can_purchase_prints": permissions.purchase_prints and bool(store) and bool(print_products),
            "store": store,
            "print_products": print_products,
            "stable_gallery_url": request.build_absolute_uri(reverse("galleries:stable_gallery_access", args=[gallery.public_id])),
            "can_share_gallery": permissions.share_gallery,
            "gallery_brand": _client_gallery_brand(gallery),
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
def client_gallery_comment(request, token, photo_id):
    token_record, invitation, gallery, permissions, _ = _client_gallery_access(token)
    if not permissions.comment:
        return HttpResponseForbidden()
    photo = get_object_or_404(
        GalleryPhoto,
        pk=photo_id,
        gallery=gallery,
        is_visible=True,
        status=GalleryPhoto.Status.COMPLETED,
    )
    body = (request.POST.get("comment") or "").strip()
    if not body:
        return redirect(f"{reverse('galleries:client_gallery_access', args=[token])}#photo-{photo.pk}")
    if len(body) > 2000:
        return HttpResponseForbidden("Comment is too long.")

    GalleryPhotoComment.objects.create(
        gallery=gallery,
        photo=photo,
        invitation=invitation,
        author=request.user if request.user.is_authenticated else None,
        body=body,
    )
    track_gallery_event(
        gallery=gallery,
        event_type=GalleryAnalyticsEvent.EventType.COMMENT,
        visitor_identifier=token_record.token_hash,
        session_identifier=_session_identifier(request),
        user=request.user,
        photo=photo,
        source="invite_link",
    )
    log_gallery_activity(
        gallery=gallery,
        event_type=GalleryActivity.EventType.CLIENT_COMMENTED,
        actor=request.user,
        actor_type=GalleryActivity.ActorType.CLIENT,
        related_object=photo,
        metadata={"client_name": invitation.client_name},
    )
    comment_count = GalleryPhotoComment.objects.filter(gallery=gallery, photo=photo).count()
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "comment_count": comment_count,
            "comment": {"author": invitation.client_name, "body": body},
        })
    return redirect(f"{reverse('galleries:client_gallery_access', args=[token])}#photo-{photo.pk}")


@require_POST
def client_gallery_favorite(request, token, photo_id):
    token_record, _, gallery, permissions, settings = _client_gallery_access(token)
    if not permissions.favorite_photos:
        return HttpResponseForbidden()
    photo = get_object_or_404(
        GalleryPhoto,
        pk=photo_id,
        gallery=gallery,
        is_visible=True,
        status=GalleryPhoto.Status.COMPLETED,
    )
    with transaction.atomic():
        # Serialize toggles for one gallery so simultaneous requests from the
        # same client cannot both observe "not favorited" and create duplicates.
        Gallery.objects.select_for_update().get(pk=gallery.pk)
        favorite_event = GalleryAnalyticsEvent.objects.filter(
            gallery=gallery,
            visitor_identifier=token_record.token_hash,
            event_type=GalleryAnalyticsEvent.EventType.FAVORITE,
            related_photo=photo,
        ).order_by("-occurred_at", "-pk").first()
        if favorite_event:
            favorite_event.delete()
            Gallery.objects.filter(pk=gallery.pk, favorite_count__gt=0).update(favorite_count=F("favorite_count") - 1)
            favorited = False
        else:
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
            favorited = True
    favorite_count = GalleryAnalyticsEvent.objects.filter(
        gallery=gallery,
        event_type=GalleryAnalyticsEvent.EventType.FAVORITE,
        related_photo=photo,
    ).count()
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"favorited": favorited, "favorite_count": favorite_count})
    return render(
        request,
        "galleries/favorite_result.html",
        {"gallery": gallery, "photo": photo, "access_token": token, "favorited": favorited},
    )


@require_GET
def client_gallery_download(request, token, photo_id):
    token_record, _, gallery, permissions, settings = _client_gallery_access(token)
    now = timezone.now()
    if not permissions.download_images:
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
    with transaction.atomic():
        # Lock the gallery while enforcing the per-client quota. Without this,
        # simultaneous requests can both observe the same remaining slot.
        Gallery.objects.select_for_update().get(pk=gallery.pk)
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


@require_GET
def client_gallery_download_original(request, token, photo_id):
    token_record, _, gallery, permissions, _ = _client_gallery_access(token)
    now = timezone.now()
    # Originals are an elevated download capability: the photographer must
    # allow downloads generally and explicitly allow original files.
    if not (permissions.download_images and permissions.download_originals):
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
    settings = GallerySettings.objects.filter(gallery=gallery).first()
    if settings and settings.download_limit is not None:
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
        source="original_download",
        metadata={"original": True},
    )
    Gallery.objects.filter(pk=gallery.pk).update(download_count=F("download_count") + 1)
    log_gallery_activity(
        gallery=gallery,
        event_type=GalleryActivity.EventType.PHOTO_DOWNLOADED,
        actor=request.user,
        actor_type=GalleryActivity.ActorType.CLIENT,
        related_object=photo,
        metadata={"original": True},
    )
    return FileResponse(photo.file.open("rb"), as_attachment=True, filename=photo.original_name)


@require_GET
def client_gallery_download_all(request, token):
    token_record, _, gallery, permissions, _ = _client_gallery_access(token)
    now = timezone.now()
    if not permissions.download_images:
        return HttpResponseForbidden()
    if permissions.download_expires_at and permissions.download_expires_at <= now:
        return HttpResponseForbidden()
    photos = GalleryPhoto.objects.filter(
        gallery=gallery,
        is_visible=True,
        status=GalleryPhoto.Status.COMPLETED,
    ).order_by("created_at", "pk")
    photo_count = photos.count()
    if not photo_count:
        raise Http404
    settings = GallerySettings.objects.filter(gallery=gallery).first()
    if settings and settings.download_limit is not None:
        used = GalleryAnalyticsEvent.objects.filter(
            gallery=gallery,
            visitor_identifier=token_record.token_hash,
            event_type=GalleryAnalyticsEvent.EventType.DOWNLOAD,
        ).count()
        if used + photo_count > settings.download_limit:
            return HttpResponseForbidden()

    # Spool larger archives to a temporary file instead of holding an entire
    # high-resolution gallery in application memory.
    archive = tempfile.SpooledTemporaryFile(max_size=16 * 1024 * 1024, mode="w+b")
    used_names = set()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as bundle:
        for photo in photos.iterator():
            base_name = photo.original_name or f"photo-{photo.pk}.jpg"
            name, suffix = base_name, 1
            while name in used_names:
                stem, dot, ext = base_name.rpartition(".")
                name = f"{stem or base_name}-{suffix}{dot}{ext}" if dot else f"{base_name}-{suffix}"
                suffix += 1
            used_names.add(name)
            with photo.file.open("rb") as source, bundle.open(name, "w", force_zip64=True) as destination:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    destination.write(chunk)
    archive.seek(0)
    track_gallery_event(gallery=gallery, event_type=GalleryAnalyticsEvent.EventType.GALLERY_DOWNLOAD,
                        visitor_identifier=token_record.token_hash, session_identifier=_session_identifier(request),
                        user=request.user, source="invite_link")
    Gallery.objects.filter(pk=gallery.pk).update(download_count=F("download_count") + photo_count)
    GalleryAnalyticsEvent.objects.bulk_create([
        GalleryAnalyticsEvent(
            photographer=gallery.photographer,
            gallery=gallery,
            visitor_identifier=token_record.token_hash,
            authenticated_user=request.user if request.user.is_authenticated else None,
            session_identifier=_session_identifier(request),
            event_type=GalleryAnalyticsEvent.EventType.DOWNLOAD,
            related_photo=photo,
            source="gallery_zip",
        )
        for photo in photos
    ])
    log_gallery_activity(gallery=gallery, event_type=GalleryActivity.EventType.GALLERY_DOWNLOADED,
                         actor=request.user, actor_type=GalleryActivity.ActorType.CLIENT)
    return FileResponse(archive, as_attachment=True, filename=f"{gallery.slug}-gallery.zip")


@require_GET
def client_gallery_print_store(request, token):
    token_record, _, gallery, permissions, _ = _client_gallery_access(token)
    if not permissions.purchase_prints:
        return HttpResponseForbidden()
    store = GalleryStore.objects.filter(gallery=gallery, enabled=True).first()
    if not store or (store.expires_at and store.expires_at <= timezone.now()):
        raise Http404
    products = list(
        StoreProduct.objects.filter(
            store=store,
            gallery=gallery,
            active=True,
            product_type__in=[
                StoreProduct.ProductType.PRINT,
                StoreProduct.ProductType.CANVAS,
                StoreProduct.ProductType.FRAMED,
                StoreProduct.ProductType.ALBUM,
            ],
        ).prefetch_related("variants")
    )
    if not products:
        raise Http404
    return render(
        request,
        "galleries/client_print_store.html",
        {
            "gallery": gallery,
            "store": store,
            "products": products,
            "access_token": token,
        },
    )


@require_POST
def client_gallery_share(request, token):
    token_record, _, gallery, permissions, _ = _client_gallery_access(token)
    if not permissions.share_gallery:
        return HttpResponseForbidden()
    stable_url = request.build_absolute_uri(
        reverse("galleries:stable_gallery_access", args=[gallery.public_id])
    )
    track_gallery_event(
        gallery=gallery,
        event_type=GalleryAnalyticsEvent.EventType.SHARE,
        visitor_identifier=token_record.token_hash,
        session_identifier=_session_identifier(request),
        user=request.user,
        source="client_gallery",
        metadata={"shared_url": stable_url},
    )
    log_gallery_activity(
        gallery=gallery,
        event_type=GalleryActivity.EventType.GALLERY_SHARED,
        actor=request.user,
        actor_type=GalleryActivity.ActorType.CLIENT,
        metadata={"shared_url": stable_url},
    )
    return redirect("galleries:client_gallery_access", token=token)


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
