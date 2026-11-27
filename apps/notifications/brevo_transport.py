"""Brevo HTTP adapter: no automatic network retries or redirects."""
import json
from email.utils import parseaddr
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError
from django.conf import settings
from django.core.validators import validate_email

class ProviderRejected(Exception):
    pass

class ProviderThrottled(Exception):
    def __init__(self, seconds):
        super().__init__("ProviderThrottled")
        self.seconds = seconds

class ProviderUncertain(Exception):
    pass

class ProviderConfigurationError(Exception):
    pass

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def submit(*, subject, plain_body, html_body, recipients, correlation):
    key = settings.BREVO_API_KEY
    name, address = parseaddr(settings.DEFAULT_FROM_EMAIL)
    try:
        validate_email(address)
    except Exception:
        raise ProviderConfigurationError() from None
    if not key or not recipients:
        raise ProviderConfigurationError()
    payload = {"sender": {"email": address}, "to": [{"email": r} for r in recipients],
        "subject": subject, "headers": {"X-Mailin-custom": correlation},
        "tags": [correlation.replace(":", "-")]}
    if name:
        payload["sender"]["name"] = name
    if html_body:
        payload["htmlContent"] = html_body
    else:
        payload["textContent"] = plain_body
    request = Request("https://api.brevo.com/v3/smtp/email", data=json.dumps(payload).encode(),
        headers={"api-key": key, "Content-Type": "application/json", "Accept": "application/json"}, method="POST")
    try:
        with build_opener(NoRedirect()).open(request, timeout=20) as response:
            if response.status != 201:
                raise ProviderUncertain()
            result = json.loads(response.read(65537))
            message_id = result.get("messageId")
            if not isinstance(message_id, str) or not 0 < len(message_id) <= 255:
                raise ProviderUncertain()
            return message_id
    except HTTPError as exc:
        if exc.code == 429:
            try:
                seconds = max(60, min(86400, int(exc.headers.get("Retry-After", "60"))))
            except (ValueError, TypeError):
                seconds = 60
            raise ProviderThrottled(seconds) from None
        if exc.code in (401, 403):
            raise ProviderConfigurationError() from None
        if exc.code in (400, 404, 413, 422):
            raise ProviderRejected() from None
        raise ProviderUncertain() from None
    except Exception:
        raise ProviderUncertain() from None
