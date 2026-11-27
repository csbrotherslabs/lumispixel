"""Authenticated encryption using an externally configured Fernet key ring."""
import json
from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def keyring():
    try:
        keys = [Fernet(key.strip().encode("ascii")) for key in settings.EMAIL_PAYLOAD_KEYS.split(",") if key.strip()]
        return MultiFernet(keys)
    except (AttributeError, ValueError, UnicodeError) as exc:
        raise ImproperlyConfigured("Configure EMAIL_PAYLOAD_KEYS with valid Fernet keys") from exc


def encrypt_payload(key, subject, plain_body, html_body):
    return keyring().encrypt(json.dumps([key, subject, plain_body, html_body]).encode()).decode("ascii")


def decrypt_payload(delivery):
    if not delivery.sensitive:
        return delivery.subject, delivery.plain_body, delivery.html_body
    key, subject, plain, html = json.loads(keyring().decrypt(delivery.encrypted_payload.encode("ascii")))
    if key != delivery.idempotency_key:
        raise ValueError("Encrypted payload does not match delivery")
    return subject, plain, html
