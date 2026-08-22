from django.conf import settings
from django.core.files.storage import FileSystemStorage


def get_private_gallery_storage():
    """Return private gallery storage without changing development behavior."""
    if settings.USE_SPACES:
        from config.storage import PrivateGalleryStorage
        return PrivateGalleryStorage()
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)
