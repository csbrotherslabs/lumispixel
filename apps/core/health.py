import socket

from django.conf import settings
from django.db import connections
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from redis import Redis


def _response(ok):
    response = JsonResponse({"status": "ok" if ok else "unavailable"}, status=200 if ok else 503)
    response["Cache-Control"] = "no-store"
    return response


@never_cache
def live(request):
    """Process liveness only; deliberately does not touch external dependencies."""
    return _response(True)


@never_cache
def ready(request):
    """Readiness for dependencies required to serve production traffic."""
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

        redis_client = Redis.from_url(
            settings.CELERY_BROKER_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        redis_client.ping()
    except Exception:
        return _response(False)

    return _response(True)
