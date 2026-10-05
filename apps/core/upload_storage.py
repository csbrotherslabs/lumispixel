"""Remote storage for non-gallery uploads; unknown paths are private by default."""
from functools import cached_property
from pathlib import PurePosixPath
from urllib.parse import quote
from uuid import uuid4

from botocore.config import Config
from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import Storage
from storages.backends.s3 import S3Storage

SITE_PREFIXES = (
    "client-profiles/", "photographer_profiles/photos/",
    "photographer_profiles/logos/", "photographer-covers/",
    "photographer_websites/",
)
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}


def is_site_image(name):
    return name.startswith(SITE_PREFIXES) and PurePosixPath(name).suffix.lower() in IMAGE_SUFFIXES


def validate_name(name):
    path = PurePosixPath(name)
    if not name or "\\" in name or path.is_absolute() or ".." in path.parts:
        raise SuspiciousFileOperation("Invalid upload object path.")
    return str(path)


class UploadB2Storage(S3Storage):
    """A private B2 origin. Public delivery is available only for site images."""
    def __init__(self, *, site=False, **kwargs):
        self.site = site
        prefix = "site" if site else "uploads"
        kwargs.update(
            access_key=settings.B2_SITE_ACCESS_KEY_ID if site else settings.B2_PRIVATE_UPLOAD_ACCESS_KEY_ID,
            secret_key=settings.B2_SITE_SECRET_ACCESS_KEY if site else settings.B2_PRIVATE_UPLOAD_SECRET_ACCESS_KEY,
            bucket_name=settings.B2_SITE_BUCKET_NAME if site else settings.B2_PRIVATE_UPLOAD_BUCKET_NAME,
            region_name=settings.B2_REGION,
            endpoint_url=settings.B2_ENDPOINT_URL,
            location=f"{prefix}/{settings.GALLERY_STORAGE_ENVIRONMENT}",
            default_acl=None,
            file_overwrite=False,
            querystring_auth=True,
            querystring_expire=settings.MEDIA_SIGNED_URL_TTL,
            custom_domain=None,
            client_config=Config(
                signature_version="s3v4",
                connect_timeout=settings.B2_CONNECT_TIMEOUT_SECONDS,
                read_timeout=settings.B2_READ_TIMEOUT_SECONDS,
                retries={"mode": "standard", "max_attempts": settings.B2_MAX_ATTEMPTS},
            ),
        )
        super().__init__(**kwargs)

    def url(self, name, parameters=None, expire=None, http_method=None):
        name = validate_name(name)
        if self.site:
            if not is_site_image(name):
                raise SuspiciousFileOperation("Only site images have public URLs.")
            key = quote(f"{self.location}/{name}", safe="/")
            return f"{settings.SITE_MEDIA_DELIVERY_BASE_URL}/{key}"
        return super().url(name, parameters=parameters, expire=expire, http_method=http_method)


class UserUploadStorage(Storage):
    """Django's default upload storage: site images vs restricted uploads."""
    @cached_property
    def site(self):
        return UploadB2Storage(site=True)

    @cached_property
    def private(self):
        return UploadB2Storage()

    def backend_for(self, name):
        name = validate_name(name)
        return self.site if is_site_image(name) else self.private

    def generate_filename(self, filename):
        # Object keys use POSIX separators even when Django runs on Windows.
        path = PurePosixPath(validate_name(str(filename)))
        return str(path.with_name(self.get_valid_name(path.name)))

    def get_available_name(self, name, max_length=None):
        path = PurePosixPath(validate_name(name))
        opaque = str(path.with_name(uuid4().hex + path.suffix.lower()))
        if max_length and len(opaque) > max_length:
            raise SuspiciousFileOperation("Upload path exceeds field length.")
        return opaque

    def _open(self, name, mode="rb"):
        return self.backend_for(name).open(name, mode)

    def _save(self, name, content):
        return self.backend_for(name).save(name, content)

    def exists(self, name):
        return self.backend_for(name).exists(name)

    def size(self, name):
        return self.backend_for(name).size(name)

    def delete(self, name):
        return self.backend_for(name).delete(name)

    def url(self, name):
        return self.backend_for(name).url(name)

    def get_modified_time(self, name):
        return self.backend_for(name).get_modified_time(name)
