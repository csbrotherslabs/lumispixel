import base64
import hashlib
import hmac
import time
from urllib.parse import quote, urlencode

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _media_path(file_name):
    name = str(file_name or "").replace("\\", "/").lstrip("/")
    if not name:
        raise ValueError("A gallery media file name is required.")

    environment = settings.GALLERY_STORAGE_ENVIRONMENT
    relative = f"private/{environment}/{name}"
    return "/" + "/".join(quote(part, safe="") for part in relative.split("/"))


def sign_media_path(path, expires):
    secret = settings.MEDIA_SIGNING_SECRET
    if not secret:
        raise ImproperlyConfigured("MEDIA_SIGNING_SECRET is required for signed media delivery.")

    payload = f"{path}\n{expires}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def signed_media_url(file_name, *, ttl=None, now=None):
    base_url = settings.MEDIA_DELIVERY_BASE_URL
    if not base_url:
        raise ImproperlyConfigured("MEDIA_DELIVERY_BASE_URL is required for signed media delivery.")

    ttl = settings.MEDIA_SIGNED_URL_TTL if ttl is None else int(ttl)
    if ttl <= 0 or ttl > 3600:
        raise ValueError("Signed media URL TTL must be between 1 and 3600 seconds.")

    now = int(time.time()) if now is None else int(now)
    expires = now + ttl
    path = _media_path(file_name)
    signature = sign_media_path(path, expires)
    query = urlencode({"expires": expires, "signature": signature})
    return f"{base_url}{path}?{query}"
