import hashlib

import logging
from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import salted_hmac

from apps.notifications.email_delivery import public_url, queue_transactional_email

logger = logging.getLogger(__name__)


def password_reset_state(user):
    # Same mutable inputs as Django's default password reset token generator.
    return salted_hmac("lumispixel.password-reset-state",
        default_token_generator._make_hash_value(user, 0), algorithm="sha256").hexdigest()


class DurablePasswordResetForm(PasswordResetForm):
    def send_mail(self, subject_template_name, email_template_name, context,
                  from_email, to_email, html_email_template_name=None):
        try:
            user = context["user"]
            origin = urlsplit(public_url())
            context = {**context, "domain": origin.netloc, "protocol": origin.scheme}
            subject = "".join(render_to_string(subject_template_name, context).splitlines())
            plain = render_to_string(email_template_name, context)
            html = render_to_string(html_email_template_name, context) if html_email_template_name else ""
            token = context["token"]
            # Django timestamps are seconds since 2001-01-01, not Unix time.
            from datetime import datetime, timezone as utc_timezone
            from django.utils.http import base36_to_int
            issued = datetime(2001, 1, 1, tzinfo=utc_timezone.utc) + timedelta(seconds=base36_to_int(token.split("-", 1)[0]))
            deadline = issued + timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT)
            if not default_token_generator.check_token(user, token):
                return
            digest = hashlib.sha256(token.encode()).hexdigest()
            queue_transactional_email(
                event_key=f"account.password_reset:{user.pk}:{digest}",
                subject=subject, plain_body=plain, html_body=html,
                recipients=[to_email], sensitive=True, expires_at=deadline,
                lifecycle_kind="account.password_reset",
                lifecycle_context={"user_id": str(user.pk), "state": password_reset_state(user)},
                supersession_scope=f"account.password_reset:{user.pk}",
            )
        except Exception as exc:
            # Match Django's non-enumerating response; never log tokens or addresses.
            logger.error("Password reset email could not be queued (%s)", type(exc).__name__)

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

    form_class = DurablePasswordResetForm

    def post(self, request, *args, **kwargs):
        email = request.POST.get("email", "")
        if not _consume_reset_attempt(request, email):
            return HttpResponse("Too many password reset attempts. Please try again later.", status=429)
        return super().post(request, *args, **kwargs)
