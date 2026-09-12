from pathlib import PurePosixPath

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage
from storages.backends.s3 import S3Storage


class PrivateGallerySpacesStorage(S3Storage):
    """Private DigitalOcean Spaces storage for gallery originals.

    Objects are isolated by environment and organized so future derivatives can
    live alongside originals without changing the gallery namespace.
    """

    default_acl = "private"
    file_overwrite = False
    querystring_auth = True

    def __init__(self, *args, **kwargs):
        required = {
            "SPACES_ACCESS_KEY": settings.SPACES_ACCESS_KEY,
            "SPACES_SECRET_KEY": settings.SPACES_SECRET_KEY,
            "SPACES_BUCKET_NAME": settings.SPACES_BUCKET_NAME,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ImproperlyConfigured(
                "DigitalOcean Spaces gallery storage is enabled but missing: "
                + ", ".join(missing)
            )

        environment = settings.SPACES_ENVIRONMENT
        if environment not in {"dev", "prod"}:
            raise ImproperlyConfigured(
                "SPACES_ENVIRONMENT must be either 'dev' or 'prod'."
            )

        kwargs.setdefault("access_key", settings.SPACES_ACCESS_KEY)
        kwargs.setdefault("secret_key", settings.SPACES_SECRET_KEY)
        kwargs.setdefault("bucket_name", settings.SPACES_BUCKET_NAME)
        kwargs.setdefault("region_name", settings.SPACES_REGION)
        kwargs.setdefault("endpoint_url", settings.SPACES_ENDPOINT_URL)
        kwargs.setdefault("querystring_auth", True)
        kwargs.setdefault("querystring_expire", settings.SPACES_SIGNED_URL_TTL)
        kwargs.setdefault("default_acl", "private")
        kwargs.setdefault("file_overwrite", False)
        kwargs.setdefault("custom_domain", None)
        kwargs.setdefault("location", f"private/{environment}")
        super().__init__(*args, **kwargs)

    def generate_filename(self, filename):
        """Place gallery uploads beneath an explicit originals namespace.

        GalleryPhoto.upload_to produces galleries/<photographer>/<gallery>/<file>.
        Spaces expands that to:
        private/<environment>/galleries/<photographer>/<gallery>/originals/<file>.
        """
        path = PurePosixPath(str(filename).replace("\\", "/"))
        parts = path.parts
        if len(parts) >= 4 and parts[0] == "galleries" and parts[3] != "originals":
            path = PurePosixPath(*parts[:3], "originals", *parts[3:])
        return super().generate_filename(str(path))


def gallery_photo_storage():
    """Resolve the gallery-original storage backend for this process.

    USE_SPACES=1 is strict: DigitalOcean Spaces is the only permitted backend and
    configuration errors are raised rather than silently falling back to disk.
    Local private storage remains available only when Spaces is explicitly off,
    which keeps local development and CI deterministic.
    """

    if settings.USE_SPACES:
        return PrivateGallerySpacesStorage()
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)
