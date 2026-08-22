from django.apps import AppConfig
from django.conf import settings


class GalleriesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.galleries"

    def ready(self):
        """Route gallery originals to private Spaces when production storage is enabled."""
        if not settings.USE_SPACES:
            return

        from .models import GalleryPhoto
        from .storage_backends import PrivateGalleryStorage

        GalleryPhoto._meta.get_field("file").storage = PrivateGalleryStorage()
