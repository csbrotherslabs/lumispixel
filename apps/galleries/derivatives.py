"""Deterministic private B2 display derivatives for gallery originals.

Paths are derived from immutable original object keys; no schema migration.
Never resize inside a web request. Celery performs work after upload.
"""
from io import BytesIO
from pathlib import PurePosixPath

from PIL import Image, ImageOps
from django.core.files.base import ContentFile

from .storage import gallery_photo_storage

VARIANTS = {"thumbnail": (640, 82), "preview": (2560, 85)}


def derivative_name(original_name, variant):
    if variant not in VARIANTS:
        raise ValueError("Unsupported derivative variant")
    original = PurePosixPath(str(original_name))
    if (len(original.parts) != 5 or original.parts[0] != "galleries"
            or original.parts[3] != "originals" or ".." in original.parts
            or not original.suffix or "\\" in str(original_name)):
        raise ValueError("Not a gallery original path")
    parts = list(original.parts)
    parts[parts.index("originals")] = "variants"
    return str(PurePosixPath(*parts[:-1], variant, original.stem + ".webp"))


def generate_photo_derivatives(photo):
    """Create both derivatives; retries safely skip existing objects.

    Source images are read through the private storage backend. EXIF orientation
    is applied; originals remain unmodified. Pillow's decompression-bomb
    protection remains enabled.
    """
    if not photo.file or photo.status != photo.Status.COMPLETED:
        return False
    storage = gallery_photo_storage()
    original_name = photo.file.name
    missing = {kind: derivative_name(original_name, kind)
               for kind in VARIANTS if not storage.exists(derivative_name(original_name, kind))}
    if not missing:
        return True
    with storage.open(original_name, "rb") as source:
        with Image.open(source) as image:
            image.load()
            for kind, target in missing.items():
                width, quality = VARIANTS[kind]
                frame = ImageOps.exif_transpose(image)
                frame.thumbnail(
                    (width, int(width * 1.5)),
                    Image.Resampling.LANCZOS,
                )
                if frame.mode not in ("RGB", "RGBA"):
                    frame = frame.convert("RGB")
                if frame.mode == "RGBA":
                    background = Image.new("RGB", frame.size, (255, 255, 255))
                    background.paste(frame, mask=frame.getchannel("A"))
                    frame = background
                output = BytesIO()
                frame.save(output, format="WEBP", quality=quality, method=4)
                output.seek(0)
                # S3Storage.save may uniquify names; use overwrite-enabled
                # storage instance so deterministic URL paths remain valid.
                storage.file_overwrite = True
                content = ContentFile(output.getvalue())
                content.content_type = "image/webp"
                saved_name = storage.save(target, content)

                if saved_name != target:
                    storage.delete(saved_name)
                    raise RuntimeError("Unexpected derivative storage path")
    return True
