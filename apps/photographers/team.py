from io import BytesIO
from uuid import uuid4
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from PIL import Image, ImageOps

KEY = "team_profiles"

def existing_team(website):
    return (website.theme_content or {}).get(KEY, [])

def team_rows(request, website, preview=False):
    old_rows = {str(row["id"]): row for row in existing_team(website)}
    indices = [i for i in request.POST.get("team_indices", "").split(",") if i]
    if len(indices) > 20 or len(set(indices)) != len(indices):
        raise ValidationError("Add no more than 20 distinct team members.")
    rows = []
    for index in indices:
        if not index.isascii() or not index.isdigit() or len(index) > 8:
            raise ValidationError("Invalid team member row.")
        prefix = f"team_{index}_"
        old = old_rows.get(request.POST.get(prefix + "id", ""), {})
        row = {key: request.POST.get(prefix + key, "").strip() for key in ("name", "role", "bio", "instagram", "url")}
        upload = request.FILES.get(prefix + "image")
        pending = preview and request.POST.get(prefix + "pending")
        if not (any(row.values()) or upload or pending or old):
            continue
        if not preview and not (row["name"] and row["role"]):
            raise ValidationError("Enter a name and role for every team member.")
        for key, limit in (("name", 120), ("role", 150), ("bio", 2000), ("instagram", 500), ("url", 500)):
            if len(row[key]) > limit:
                raise ValidationError("Team member information is too long.")
        for key in ("instagram", "url"):
            if row[key]:
                try:
                    URLValidator(schemes=["http", "https"])(row[key])
                except ValidationError:
                    if not preview:
                        raise ValidationError("Enter valid HTTP or HTTPS team profile links.")
                    row[key] = ""
        row.update(id=old.get("id") or uuid4().hex, image="" if request.POST.get(prefix + "clear") else old.get("image", ""), preview_index=index)
        if upload and not preview:
            if upload.size > 50 * 1024 * 1024:
                raise ValidationError("Team photographs must be 50 MB or smaller.")
            try:
                with Image.open(upload) as im:
                    if im.format not in {"JPEG", "PNG", "WEBP"} or im.width * im.height > 25000000:
                        raise ValueError("Unsupported image")
                    im = ImageOps.exif_transpose(im).convert("RGB")
                    im.thumbnail((1000, 1000))
                    out = BytesIO()
                    im.save(out, format="WEBP", quality=85)
                    row["upload"] = out.getvalue()
            except (OSError, ValueError, Image.DecompressionBombError):
                raise ValidationError("Upload a valid JPEG, PNG or WebP photograph up to 25 megapixels.")
        rows.append(row)
    return rows

def save_team(website, rows):
    for row in rows:
        upload = row.pop("upload", None)
        row.pop("preview_index", None)
        if upload:
            row["image"] = website.hero_image.storage.save(f"photographer-team/{website.pk}/{uuid4().hex}.webp", ContentFile(upload))
    website.theme_content = dict(website.theme_content or {}, **{KEY: rows})
    website.save(update_fields=["theme_content", "updated_at"])
