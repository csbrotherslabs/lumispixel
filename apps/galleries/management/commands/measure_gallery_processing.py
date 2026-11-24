"""Observe newly completed uploads and derivative readiness without writing data."""
import json
import statistics
import time

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from apps.galleries.models import Gallery, GalleryPhoto
from apps.galleries.derivatives import derivative_name
from apps.galleries.storage import gallery_photo_storage


class Command(BaseCommand):
    help = "Watch a bounded batch of new gallery uploads and inspect B2 derivative metadata."

    def add_arguments(self, parser):
        parser.add_argument("--gallery-id", type=int, required=True)
        parser.add_argument("--count", type=int, default=25)
        parser.add_argument("--timeout", type=int, default=1800)
        parser.add_argument("--interval", type=int, default=10)

    def handle(self, *args, **options):
        if not settings.DEBUG or settings.GALLERY_STORAGE_ENVIRONMENT != "dev" or settings.GALLERY_STORAGE_BACKEND != "b2":
            raise CommandError("Requires DEBUG and development B2 storage.")
        count, timeout, interval = (options[k] for k in ("count", "timeout", "interval"))
        if not 1 <= count <= 500 or not 10 <= timeout <= 7200 or not 5 <= interval <= 60:
            raise CommandError("Count 1–500, timeout 10–7200s, interval 5–60s.")
        if not Gallery.objects.filter(pk=options["gallery_id"], deleted_at__isnull=True).exists():
            raise CommandError("Gallery not found.")
        photos = GalleryPhoto.objects.filter(gallery_id=options["gallery_id"])
        baseline = photos.order_by("-pk").values_list("pk", flat=True).first() or 0
        storage = gallery_photo_storage()
        if storage.location.strip("/") != "private/dev":
            raise CommandError("Unexpected storage prefix.")
        client = storage.connection.meta.client
        start = time.monotonic()
        seen = {}
        ready = {}
        metadata = {}
        self.stdout.write(f"READY: upload exactly {count} new photos to gallery {options['gallery_id']} now. Baseline photo ID: {baseline}.")
        self.stdout._out.flush()
        while time.monotonic() - start < timeout:
            batch = list(photos.filter(pk__gt=baseline).order_by("pk")[:count])
            for photo in batch:
                if time.monotonic() - start >= timeout:
                    break
                if photo.status != GalleryPhoto.Status.COMPLETED or not photo.file:
                    continue
                seen.setdefault(photo.pk, (time.monotonic(), photo.file_size))
                if photo.pk in ready:
                    continue
                for kind in ("thumbnail", "preview"):
                    if time.monotonic() - start >= timeout:
                        break
                    key = (photo.pk, kind)
                    if key in metadata:
                        continue
                    name = derivative_name(photo.file.name, kind)
                    try:
                        head = client.head_object(Bucket=storage.bucket_name, Key=f"{storage.location.strip('/')}/{name}")
                    except ClientError as exc:
                        if str(exc.response.get("Error", {}).get("Code")) in {"404", "NoSuchKey", "NotFound"}:
                            continue
                        raise CommandError(f"B2 metadata check failed: {exc.response.get('Error', {}).get('Code')}") from exc
                    if head.get("ContentType") != "image/webp" or head.get("ContentLength", 0) <= 0:
                        raise CommandError(f"Invalid derivative metadata for photo {photo.pk}, {kind}.")
                    metadata[key] = head["ContentLength"]
                if all((photo.pk, kind) in metadata for kind in ("thumbnail", "preview")):
                    ready[photo.pk] = time.monotonic()
            elapsed = time.monotonic() - start
            self.stdout.write(f"{elapsed:.1f}s: completed originals {len(seen)}/{count}; thumbnails {sum(k[1]=='thumbnail' for k in metadata)}; both variants {len(ready)}/{count}")
            self.stdout._out.flush()
            if len(ready) == count:
                break
            time.sleep(min(interval, max(0, timeout - elapsed)))
        elapsed = time.monotonic() - start
        delays = [t - seen[pk][0] for pk, t in ready.items()]
        sizes = [size for (pk, kind), size in metadata.items() if kind == "thumbnail"]
        self.stdout.write(json.dumps({
            "gallery_id": options["gallery_id"], "expected": count,
            "completed_originals_observed": len(seen), "both_variants_observed": len(ready),
            "original_bytes_observed": sum(v[1] for v in seen.values()),
            "elapsed_seconds": round(elapsed, 2),
            "median_observed_readiness_delay_seconds": round(statistics.median(delays), 2) if delays else None,
            "max_observed_readiness_delay_seconds": round(max(delays), 2) if delays else None,
            "mean_thumbnail_bytes": round(statistics.mean(sizes)) if sizes else None,
            "poll_interval_seconds": interval,
            "scope": "Polling observations, not exact upload, task runtime or queue wait measurements",
            "incomplete_photo_ids": sorted(set(seen) - set(ready)),
            "passed": len(ready) == count,
        }, indent=2))
        if len(ready) != count:
            raise CommandError("Batch readiness not fully observed before timeout.")
