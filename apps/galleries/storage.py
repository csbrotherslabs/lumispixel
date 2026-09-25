from pathlib import PurePosixPath

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage
from storages.backends.s3 import S3Storage


class PrivateGalleryObjectStorage(S3Storage):
    """Shared behavior for private S3-compatible gallery-original storage."""

    default_acl = "private"
    file_overwrite = False
    querystring_auth = True

    def generate_filename(self, filename):
        """Place gallery uploads beneath an explicit originals namespace."""
        path = PurePosixPath(str(filename).replace("\\", "/"))
        parts = path.parts
        if len(parts) >= 4 and parts[0] == "galleries" and parts[3] != "originals":
            path = PurePosixPath(*parts[:3], "originals", *parts[3:])
        return super().generate_filename(str(path))


class PrivateGalleryB2Storage(PrivateGalleryObjectStorage):
    """Private Backblaze B2 storage using B2's S3-compatible API."""

    def __init__(self, *args, **kwargs):
        required = {
            "B2_ACCESS_KEY_ID": settings.B2_ACCESS_KEY_ID,
            "B2_SECRET_ACCESS_KEY": settings.B2_SECRET_ACCESS_KEY,
            "B2_BUCKET_NAME": settings.B2_BUCKET_NAME,
            "B2_REGION": settings.B2_REGION,
            "B2_ENDPOINT_URL": settings.B2_ENDPOINT_URL,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ImproperlyConfigured(
                "Backblaze B2 gallery storage is enabled but missing: "
                + ", ".join(missing)
            )

        kwargs.setdefault("access_key", settings.B2_ACCESS_KEY_ID)
        kwargs.setdefault("secret_key", settings.B2_SECRET_ACCESS_KEY)
        kwargs.setdefault("bucket_name", settings.B2_BUCKET_NAME)
        kwargs.setdefault("region_name", settings.B2_REGION)
        kwargs.setdefault("endpoint_url", settings.B2_ENDPOINT_URL)
        kwargs.setdefault("querystring_auth", True)
        kwargs.setdefault("querystring_expire", settings.B2_SIGNED_URL_TTL)
        kwargs.setdefault("default_acl", "private")
        kwargs.setdefault("file_overwrite", False)
        kwargs.setdefault("custom_domain", None)
        kwargs.setdefault("location", f"private/{settings.GALLERY_STORAGE_ENVIRONMENT}")
        kwargs.setdefault(
            "client_config",
            {
                "connect_timeout": settings.B2_CONNECT_TIMEOUT_SECONDS,
                "read_timeout": settings.B2_READ_TIMEOUT_SECONDS,
                "retries": {
                    "mode": "standard",
                    "max_attempts": settings.B2_MAX_ATTEMPTS,
                },
            },
        )
        super().__init__(*args, **kwargs)



def gallery_photo_storage():
    """Resolve gallery-original storage without coupling models to a provider."""
    backend = settings.GALLERY_STORAGE_BACKEND
    if backend == "b2":
        return PrivateGalleryB2Storage()
    if backend == "local":
        return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)
    raise ImproperlyConfigured(f"Unsupported gallery storage backend: {backend}")
