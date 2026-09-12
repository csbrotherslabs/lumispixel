from django.conf import settings
from storages.backends.s3 import S3Storage


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
