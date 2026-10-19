"""Independent semantic indexing and durable purge entry points."""
import logging
from celery import shared_task
from django.conf import settings
from apps.galleries.models import Gallery, GalleryPhoto
from .models import GallerySemanticSearchPolicy
from .semantic import semantic_enabled, embed_image, replace_photo, purge_gallery

logger=logging.getLogger(__name__)

@shared_task
def index_semantic_gallery(gallery_id):
    if not semantic_enabled() or not getattr(settings,"VISUAL_SEARCH_SEMANTIC_POLICY_APPROVED",False):
        return "disabled"
    gallery=Gallery.objects.filter(pk=gallery_id,deleted_at__isnull=True,archived_at__isnull=True).first()
    if not gallery or not GallerySemanticSearchPolicy.objects.filter(gallery=gallery,processing_authorized=True).exists():
        return "unauthorized"
    count=0
    for photo in GalleryPhoto.objects.filter(gallery=gallery,status=GalleryPhoto.Status.COMPLETED).exclude(file="").iterator():
        if not GallerySemanticSearchPolicy.objects.filter(gallery=gallery,processing_authorized=True).exists():
            return "revoked"
        try:
            with photo.file.open("rb") as stream:
                vector=embed_image(stream)
            if not GallerySemanticSearchPolicy.objects.filter(gallery=gallery,processing_authorized=True).exists():
                return "revoked"
            replace_photo(photo=photo,vector=vector)
            count+=1
        except Exception:
            logger.exception("Semantic indexing failed for photo %s",photo.pk)
            raise
    return count

@shared_task(bind=True,max_retries=5)
def purge_semantic_gallery(self,gallery_id):
    try:
        purge_gallery(gallery_id)
        return "purged"
    except Exception as exc:
        raise self.retry(exc=exc,countdown=min(60*(2**self.request.retries),3600))
