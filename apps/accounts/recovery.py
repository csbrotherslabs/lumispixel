import hashlib

from django.contrib.auth import views as auth_views
from django.core.cache import cache
from django.http import HttpResponse

PASSWORD_RESET_LIMIT = 5
PASSWORD_RESET_WINDOW_SECONDS = 15 * 60


def _reset_key(request, email):
    normalized = (email or "").strip().casefold()
    identity = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    remote = forwarded or request.META.get("REMOTE_ADDR") or "unknown"
    ip_hash = hashlib.sha256(remote.encode("utf-8")).hexdigest()[:24]
    return f"password-reset:{identity}:{ip_hash}"


def _consume_reset_attempt(request, email):
    key = _reset_key(request, email)
    try:
        attempts = cache.incr(key)
    except ValueError:
        cache.set(key, 1, PASSWORD_RESET_WINDOW_SECONDS)
        attempts = 1
    else:
        cache.touch(key, PASSWORD_RESET_WINDOW_SECONDS)
    return attempts <= PASSWORD_RESET_LIMIT


class RateLimitedPasswordResetView(auth_views.PasswordResetView):
    """Preserve Django's non-enumerating reset behavior while bounding abuse."""

    def post(self, request, *args, **kwargs):
        email = request.POST.get("email", "")
        if not _consume_reset_attempt(request, email):
            return HttpResponse("Too many password reset attempts. Please try again later.", status=429)
        return super().post(request, *args, **kwargs)
