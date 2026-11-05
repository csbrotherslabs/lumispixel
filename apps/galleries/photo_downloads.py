"""Bounded JPEG derivatives; original downloads use their separate permission route."""
from io import BytesIO
from PIL import Image, ImageOps

DOWNLOAD_EDGES = {'small': 1280, 'medium': 2048, 'large': 3840}


def resized_download(photo, size):
    photo.file.open('rb')
    try:
        with Image.open(photo.file) as source:
            image = ImageOps.exif_transpose(source)
            image.thumbnail((DOWNLOAD_EDGES[size], DOWNLOAD_EDGES[size]), Image.Resampling.LANCZOS)
            output = BytesIO()
            image.convert('RGB').save(output, format='JPEG', quality=90)
            output.seek(0)
            return output
    finally:
        photo.file.close()
