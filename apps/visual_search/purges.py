"""Transactional outbox for durable, idempotent biometric vector deletion."""
import logging
from datetime import timedelta
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from .models import FaceVectorPurge

logger = logging.getLogger(__name__)


def enqueue_purge(kind, object_id):
    if kind not in ("photo", "gallery"):
        raise ValueError("Unsupported purge kind")
    purge = FaceVectorPurge.objects.create(kind=kind, object_id=object_id)
    transaction.on_commit(lambda pk=purge.pk: dispatch_purge(pk))
    return purge


def dispatch_purge(pk):
    from .tasks import process_vector_purge
    try:
        process_vector_purge.delay(pk)
    except Exception:
        logger.exception("Vector purge %s dispatch failed; outbox retained", pk)


def execute_purge(pk):
    with transaction.atomic():
        purge = FaceVectorPurge.objects.select_for_update().filter(pk=pk).first()
        if not purge or purge.status == FaceVectorPurge.Status.COMPLETED:
            return "already_completed"
        if purge.status == FaceVectorPurge.Status.PROCESSING:
            return "already_processing"
        token = uuid4()
        purge.status = FaceVectorPurge.Status.PROCESSING
        purge.claim_token = token
        purge.started_at = timezone.now()
        purge.attempts += 1
        purge.save(update_fields=["status", "claim_token", "started_at", "attempts", "updated_at"])
        kind, object_id = purge.kind, purge.object_id
    try:
        from .vector_store import delete_gallery_embeddings, delete_photo_embeddings
        if kind == "gallery":
            delete_gallery_embeddings(object_id)
        else:
            delete_photo_embeddings(object_id)
    except Exception as exc:
        logger.exception("Vector purge %s failed", pk)
        with transaction.atomic():
            current = FaceVectorPurge.objects.select_for_update().get(pk=pk)
            if current.claim_token == token and current.status == FaceVectorPurge.Status.PROCESSING:
                current.status = FaceVectorPurge.Status.PENDING
                current.claim_token = None
                current.last_error = str(exc)[:1000]
                current.save(update_fields=["status", "claim_token", "last_error", "updated_at"])
        return "retry_pending"
    with transaction.atomic():
        current = FaceVectorPurge.objects.select_for_update().get(pk=pk)
        if current.claim_token == token and current.status == FaceVectorPurge.Status.PROCESSING:
            current.status = FaceVectorPurge.Status.COMPLETED
            current.claim_token = None
            current.last_error = ""
            current.save(update_fields=["status", "claim_token", "last_error", "updated_at"])
    return "completed"


def recover_and_dispatch_purges():
    cutoff = timezone.now() - timedelta(minutes=30)
    with transaction.atomic():
        stale = list(FaceVectorPurge.objects.select_for_update().filter(
            status=FaceVectorPurge.Status.PROCESSING, started_at__lt=cutoff
        )[:100])
        for purge in stale:
            purge.status = FaceVectorPurge.Status.PENDING
            purge.claim_token = None
            purge.save(update_fields=["status", "claim_token", "updated_at"])
    ids = list(FaceVectorPurge.objects.filter(status=FaceVectorPurge.Status.PENDING)
               .order_by("created_at").values_list("pk", flat=True)[:100])
    for pk in ids:
        dispatch_purge(pk)
    return len(ids)
