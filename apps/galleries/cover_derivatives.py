"""Generate cover-only display objects without copying the original."""
import hashlib
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

from .derivatives import derivative_name
from .storage import gallery_photo_storage

COVER_VARIANTS = {"thumbnail": (960, 80, 100_000), "preview": (1920, 82, 250_000)}


def cover_media_name(gallery):
    digest = hashlib.sha256(gallery.cover_image.name.encode("utf-8")).hexdigest()
    return f"galleries/covers-v2/{gallery.pk}/originals/{digest}.jpg"


def generate_cover_derivatives(gallery):
    if not gallery.cover_image:
        return False
    storage = gallery_photo_storage()
    name = cover_media_name(gallery)
    missing = {kind: derivative_name(name, kind) for kind in COVER_VARIANTS
               if not storage.exists(derivative_name(name, kind))}
    if not missing:
        return True
    with gallery.cover_image.open("rb") as source:
        with Image.open(source) as image:
            frame = ImageOps.exif_transpose(image).convert("RGB")
            for kind, target in missing.items():
                width, quality, budget = COVER_VARIANTS[kind]
                resized = frame.copy()
                resized.thumbnail((width, width), Image.Resampling.LANCZOS)
                while True:
                    output = BytesIO()
                    resized.save(output, format="WEBP", quality=quality, method=4)
                    if output.tell() <= budget or quality <= 55:
                        break
                    quality = max(55, quality - 5)
                content = ContentFile(output.getvalue())
                content.content_type = "image/webp"
                storage.file_overwrite = True
                saved = storage.save(target, content)
                if saved != target:
                    storage.delete(saved)
                    raise RuntimeError("Unexpected cover derivative path")
    return True
