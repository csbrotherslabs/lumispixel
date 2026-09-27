import tempfile
import zipfile
from contextlib import closing
from pathlib import PurePosixPath

from django.db.models import F
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.utils import timezone
from django.views.decorators.http import require_GET

from .activity import log_gallery_activity
from .analytics import track_gallery_event
from .models import Gallery, GalleryActivity, GalleryAnalyticsEvent, GalleryPhoto, GallerySettings
from .views import _client_gallery_access, _session_identifier


def _safe_archive_name(original_name, photo_id):
    """Return a flat, client-safe ZIP member name."""
    name = PurePosixPath((original_name or "").replace("\\", "/")).name
    return name or f"photo-{photo_id}.jpg"


def _copy_photo_to_zip(photo, bundle, archive_name):
    """Copy a storage-backed photo into a ZIP without assuming a local file.

    django-storages/B2 file objects are explicitly opened and closed here rather
    than relying on local-file context-manager behavior.
    """
    photo.file.open("rb")
    source = photo.file.file
    try:
        with bundle.open(archive_name, "w", force_zip64=True) as destination:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                destination.write(chunk)
    finally:
        photo.file.close()


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

    archive = tempfile.SpooledTemporaryFile(max_size=16 * 1024 * 1024, mode="w+b")
    used_names = set()
    downloaded_photos = []
    try:
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as bundle:
            for photo in photos.iterator():
                base_name = _safe_archive_name(photo.original_name, photo.pk)
                name = base_name
                suffix = 1
                while name in used_names:
                    path = PurePosixPath(base_name)
                    stem = path.stem or f"photo-{photo.pk}"
                    extension = path.suffix
                    name = f"{stem}-{suffix}{extension}"
                    suffix += 1
                used_names.add(name)
                _copy_photo_to_zip(photo, bundle, name)
                downloaded_photos.append(photo)
        archive.seek(0)
    except Exception:
        archive.close()
        raise

    track_gallery_event(
        gallery=gallery,
        event_type=GalleryAnalyticsEvent.EventType.GALLERY_DOWNLOAD,
        visitor_identifier=token_record.token_hash,
        session_identifier=_session_identifier(request),
        user=request.user,
        source="invite_link",
    )
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
        for photo in downloaded_photos
    ])
    log_gallery_activity(
        gallery=gallery,
        event_type=GalleryActivity.EventType.GALLERY_DOWNLOADED,
        actor=request.user,
        actor_type=GalleryActivity.ActorType.CLIENT,
    )
    return FileResponse(archive, as_attachment=True, filename=f"{gallery.slug}-gallery.zip")
