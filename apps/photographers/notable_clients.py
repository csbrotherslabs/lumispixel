from io import BytesIO
from uuid import uuid4
from django.core.files.base import ContentFile
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from PIL import Image, ImageOps

KEY = "notable_clients"
LIMIT = 20


def existing_clients(website):
    return (website.theme_content or {}).get(KEY, [])


def client_rows(request, website, preview=False):
    existing = {str(item["id"]): item for item in existing_clients(website)}
    rows = []
    indices = request.POST.get("client_indices", "").split(",")
    indices = [i for i in indices if i]
    if len(indices) > LIMIT or len(set(indices)) != len(indices):
        raise ValidationError("Add no more than 20 distinct clients.")
    for index in indices:
        if not index.isascii() or not index.isdigit() or len(index) > 8:
            raise ValidationError("Invalid client row.")
        prefix = f"client_{index}_"
        name = request.POST.get(prefix + "name", "").strip()
        url = request.POST.get(prefix + "url", "").strip()
        old = existing.get(request.POST.get(prefix + "id", ""), {})
        upload = request.FILES.get(prefix + "image")
        pending = preview and request.POST.get(prefix + "pending")
        if not (name or url or upload or pending or old):
            continue
        if not name and not preview:
            raise ValidationError("Enter a name for each notable client.")
        if len(name) > 120 or len(url) > 500:
            raise ValidationError("Client name or URL is too long.")
        if url:
            try:
                URLValidator(schemes=["http", "https"])(url)
            except ValidationError:
                if not preview:
                    raise ValidationError("Enter a valid HTTP or HTTPS client website.")
                url = ""
        row = {"id": old.get("id") or uuid4().hex, "name": name, "url": url,
               "image": "" if request.POST.get(prefix + "clear") else old.get("image", ""),
               "preview_index": index}
        if upload and not preview:
            if upload.size > 50 * 1024 * 1024:
                raise ValidationError("Client logos must be 50 MB or smaller.")
            try:
                with Image.open(upload) as im:
                    if im.format not in {"PNG", "JPEG", "WEBP"} or im.width * im.height > 25000000:
                        raise ValueError("Unsupported logo")
                    im = ImageOps.exif_transpose(im).convert("RGBA")
                    im.thumbnail((1200, 1200))
                    out = BytesIO()
                    im.save(out, format="WEBP", lossless=True)
                    row["upload"] = out.getvalue()
            except (OSError, ValueError, Image.DecompressionBombError):
                raise ValidationError("Upload a valid PNG, JPEG or WebP logo up to 25 megapixels.")
        rows.append(row)
    return rows


def save_clients(website, rows):
    storage = website.hero_image.storage
    for row in rows:
        upload = row.pop("upload", None)
        row.pop("preview_index", None)
        if upload:
            row["image"] = storage.save(f"photographer-client-logos/{website.pk}/{uuid4().hex}.webp", ContentFile(upload))
    website.theme_content = dict(website.theme_content or {}, **{KEY: rows})
    website.save(update_fields=["theme_content", "updated_at"])
