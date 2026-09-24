from datetime import timedelta
import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import GalleryMultipartUpload
from .multipart_uploads import abort as abort_multipart

logger = logging.getLogger(__name__)


def cleanup_stale_multipart_uploads(*, now=None):
    """Abort stale B2 multipart sessions and release their reserved quota.

    A session is stale only after it has been inactive in LumisPixel for the
    configured recovery window. Failed B2 aborts remain active so a later run
    can retry them instead of silently releasing quota while storage still
    holds an unfinished multipart upload.
    """
    now = now or timezone.now()
    cutoff = now - timedelta(seconds=settings.B2_MULTIPART_STALE_AFTER_SECONDS)
    stale = GalleryMultipartUpload.objects.filter(
        completed_at__isnull=True,
        aborted_at__isnull=True,
        created_at__lt=cutoff,
    ).order_by("created_at")

    aborted = 0
    failed = 0
    for session in stale.iterator():
        try:
            abort_multipart(key=session.object_key, upload_id=session.upload_id)
        except Exception:
            failed += 1
            logger.exception("Could not abort stale multipart upload %s", session.pk)
            continue
        updated = GalleryMultipartUpload.objects.filter(
            pk=session.pk,
            completed_at__isnull=True,
            aborted_at__isnull=True,
        ).update(aborted_at=now)
        aborted += updated
    return {"aborted": aborted, "failed": failed}


@shared_task
def cleanup_stale_gallery_multipart_uploads():
    return cleanup_stale_multipart_uploads()
