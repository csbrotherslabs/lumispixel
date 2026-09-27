import logging

from django.conf import settings
from django.db import connections
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from redis import Redis

from apps.galleries.storage import gallery_photo_storage


logger = logging.getLogger(__name__)


def _response(ok):
    response = JsonResponse({"status": "ok" if ok else "unavailable"}, status=200 if ok else 503)
    response["Cache-Control"] = "no-store"
    return response


def _database_ready():
    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()


def _broker_ready():
    redis_client = Redis.from_url(
        settings.CELERY_BROKER_URL,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    redis_client.ping()


def _storage_ready():
    if settings.GALLERY_STORAGE_BACKEND != "b2":
        return
    storage = gallery_photo_storage()
    storage.bucket.meta.client.head_bucket(Bucket=settings.B2_BUCKET_NAME)


@never_cache
def live(request):
    """Process liveness only; deliberately does not touch external dependencies."""
    return _response(True)


@never_cache
def ready(request):
    """Readiness for dependencies required to serve production traffic.

    The public response deliberately stays generic. Dependency identity and
    provider exception text belong in server-side observability, not HTTP.
    """
    for dependency, check in (
        ("database", _database_ready),
        ("celery_broker", _broker_ready),
        ("gallery_storage", _storage_ready),
    ):
        try:
            check()
        except Exception:
            logger.exception("Readiness dependency failed", extra={"dependency": dependency})
            return _response(False)

    return _response(True)
