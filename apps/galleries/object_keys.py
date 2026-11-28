"""Fail-closed gallery object namespace validation."""
from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation


def validate_relative_gallery_name(name):
    if not isinstance(name, str) or not name or any(
        c in name for c in ("\\", "%", "?", "#")
    ) or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise SuspiciousFileOperation("Invalid gallery object path.")
    parts = name.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise SuspiciousFileOperation("Invalid gallery object path.")
    if len(parts) < 4 or parts[0] != "galleries":
        raise SuspiciousFileOperation("Invalid gallery namespace.")
    if not (parts[2].isascii() and parts[2].isdecimal() and
            (parts[1] == "covers-v2" or (parts[1].isascii() and parts[1].isdecimal()))):
        raise SuspiciousFileOperation("Invalid gallery identity.")
    if not (
        (len(parts) == 5 and parts[3] == "originals")
        or (len(parts) == 6 and parts[3] == "variants"
            and parts[4] in ("thumbnail", "preview") and parts[5].endswith(".webp"))
        or (len(parts) == 4 and parts[1] != "covers-v2" and parts[3] not in ("originals", "variants"))
    ):
        raise SuspiciousFileOperation("Invalid gallery object layout.")
    return name


def validate_gallery_object_key(key):
    environment = settings.GALLERY_STORAGE_ENVIRONMENT
    if environment not in ("dev", "prod"):
        raise SuspiciousFileOperation("Invalid gallery storage environment.")
    prefix = f"private/{environment}/"
    if not isinstance(key, str) or not key.startswith(prefix):
        raise SuspiciousFileOperation("Gallery object outside current environment.")
    validate_relative_gallery_name(key[len(prefix):])
    return key
