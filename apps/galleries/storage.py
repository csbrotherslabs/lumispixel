from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage
from storages.backends.s3 import S3Storage


class PrivateGallerySpacesStorage(S3Storage):
    """Private DigitalOcean Spaces storage for gallery originals.

    Gallery media remains private and is accessed through application-authorized
    views or short-lived signed object URLs. Public ACLs and overwrite behavior
    are intentionally disabled.
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
        kwargs.setdefault("location", "private")
        super().__init__(*args, **kwargs)


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
