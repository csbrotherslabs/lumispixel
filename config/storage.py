from django.conf import settings
from storages.backends.s3 import S3Storage


class PrivateGalleryStorage(S3Storage):
    """Private object storage for gallery originals.

    Objects are never public. Django/storage URLs are signed and expire after
    the configured query-string lifetime.
    """

    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    location = settings.GALLERY_STORAGE_LOCATION
    default_acl = None
    file_overwrite = False
    querystring_auth = True
    querystring_expire = settings.AWS_QUERYSTRING_EXPIRE
