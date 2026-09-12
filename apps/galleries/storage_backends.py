from django.conf import settings
from django.core.files.storage import FileSystemStorage
from storages.backends.s3 import S3Storage


class PrivateGalleryFileSystemStorage(FileSystemStorage):
    """Private local storage whose migration identity is environment-independent.

    Passing an absolute PRIVATE_MEDIA_ROOT directly to FileSystemStorage causes
    Django migrations to serialize a machine-specific path. Instantiating this
    subclass without constructor arguments keeps migration state stable while
    resolving the actual private-media location at runtime.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("location", settings.PRIVATE_MEDIA_ROOT)
        super().__init__(*args, **kwargs)


class PrivateGalleryStorage(S3Storage):
    bucket_name = settings.SPACES_BUCKET_NAME
    endpoint_url = settings.SPACES_ENDPOINT_URL
    region_name = settings.SPACES_REGION
    access_key = settings.SPACES_ACCESS_KEY
    secret_key = settings.SPACES_SECRET_KEY
    location = "gallery-originals"
    default_acl = None
    file_overwrite = False
    querystring_auth = True
    querystring_expire = settings.SPACES_SIGNED_URL_TTL
