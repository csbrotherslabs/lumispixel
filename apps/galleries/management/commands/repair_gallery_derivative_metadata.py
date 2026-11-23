from pathlib import PurePosixPath

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from PIL import Image

from apps.galleries.models import GalleryPhoto
from apps.galleries.storage import PrivateGalleryB2Storage


class Command(BaseCommand):
    help = "Audit development gallery WebP metadata; writes require --apply."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--gallery-id", type=int)
        parser.add_argument("--photo-id", type=int)

    def handle(self, *args, **options):
        if settings.GALLERY_STORAGE_ENVIRONMENT != "dev" or settings.GALLERY_STORAGE_BACKEND != "b2":
            raise CommandError("This command is restricted to development B2 storage.")
        if options["apply"] and options["dry_run"]:
            raise CommandError("Choose either --apply or --dry-run.")
        storage = PrivateGalleryB2Storage()
        if storage.location.strip("/") != "private/dev":
            raise CommandError("Unexpected storage prefix.")
        client = storage.connection.meta.client
        bucket = storage.bucket_name
        photos = GalleryPhoto.objects.all()
        if options["gallery_id"] is not None:
            photos = photos.filter(gallery_id=options["gallery_id"])
        if options["photo_id"] is not None:
            photos = photos.filter(pk=options["photo_id"])
        counts = dict(correct=0, needs_repair=0, repaired=0, missing=0, failed=0)
        for photo in photos.iterator():
            path = PurePosixPath(photo.file.name)
            if len(path.parts) != 5 or path.parts[0] != "galleries" or path.parts[-2] != "originals" or ".." in path.parts:
                counts["failed"] += 1
                self.stderr.write(f"Photo {photo.pk}: unexpected original path")
                continue
            for variant in ("thumbnail", "preview"):
                relative = str(path.parent.parent / "variants" / variant / (path.stem + ".webp"))
                key = "private/dev/" + relative
                try:
                    head = client.head_object(Bucket=bucket, Key=key)
                    if head.get("ContentType") == "image/webp":
                        counts["correct"] += 1
                        continue
                    counts["needs_repair"] += 1
                    self.stdout.write(f"{key}: {head.get('ContentType')} -> image/webp")
                    if not options["apply"]:
                        continue
                    with storage.open(relative, "rb") as stream:
                        with Image.open(stream) as image:
                            if image.format != "WEBP":
                                raise ValueError("Not a WebP image")
                            image.verify()
                    metadata = {name: head[name] for name in (
                        "Metadata", "CacheControl", "ContentDisposition",
                        "ContentEncoding", "ContentLanguage", "Expires",
                    ) if name in head}
                    source = {"Bucket": bucket, "Key": key}
                    if head.get("VersionId") and head["VersionId"] != "null":
                        source["VersionId"] = head["VersionId"]
                    client.copy_object(
                        Bucket=bucket, Key=key, CopySource=source,
                        CopySourceIfMatch=head["ETag"], MetadataDirective="REPLACE",
                        ContentType="image/webp", **metadata,
                    )
                    updated = client.head_object(Bucket=bucket, Key=key)
                    if updated.get("ContentType") != "image/webp" or updated["ContentLength"] != head["ContentLength"]:
                        raise ValueError("Post-copy metadata or length verification failed")
                    counts["repaired"] += 1
                except ClientError as exc:
                    code = exc.response.get("Error", {}).get("Code", "")
                    if code in {"404", "NoSuchKey", "NotFound"}:
                        counts["missing"] += 1
                    else:
                        counts["failed"] += 1
                    self.stderr.write(f"{key}: {code}")
                except Exception as exc:
                    counts["failed"] += 1
                    self.stderr.write(f"{key}: {type(exc).__name__}")
        self.stdout.write(("APPLY" if options["apply"] else "DRY RUN") + ": " + ", ".join(f"{k}={v}" for k, v in counts.items()))
        if counts["failed"]:
            raise CommandError("Some derivatives could not be processed.")
