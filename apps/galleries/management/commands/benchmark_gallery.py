"""Measure real client pagination without persisting synthetic galleries."""
import json
import statistics
import time
import tracemalloc
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext

from apps.galleries.models import Gallery, GalleryPhoto
from apps.galleries.views import _paginate_client_gallery_photos, _prepare_client_gallery_content


class Command(BaseCommand):
    help = "Benchmark synthetic gallery pagination inside a rolled-back transaction."

    def add_arguments(self, parser):
        parser.add_argument("--source-gallery-id", type=int, required=True)
        parser.add_argument("--count", type=int, default=100)
        parser.add_argument("--iterations", type=int, default=10)

    def handle(self, *args, **options):
        if not settings.DEBUG or settings.GALLERY_STORAGE_ENVIRONMENT != "dev":
            raise CommandError("This benchmark requires DEBUG and dev gallery storage.")
        count, iterations = options["count"], options["iterations"]
        if not 1 <= count <= 10000 or not 1 <= iterations <= 30:
            raise CommandError("Count must be 1–10000 and iterations 1–30.")
        if connection.in_atomic_block:
            raise CommandError("Run this command outside an existing transaction.")
        with transaction.atomic():
            try:
                source = Gallery.objects.get(pk=options["source_gallery_id"], deleted_at__isnull=True)
            except Gallery.DoesNotExist:
                raise CommandError("Source gallery not found.")
            originals = list(source.photos.filter(
                status=GalleryPhoto.Status.COMPLETED, is_visible=True
            ).exclude(file="").order_by("pk").values_list("file", flat=True)[:60])
            if not originals:
                raise CommandError("Source gallery has no completed visible photos.")
            marker = uuid.uuid4().hex
            gallery = Gallery.objects.bulk_create([Gallery(
                photographer_id=source.photographer_id,
                name="BENCHMARK " + marker,
                slug="benchmark-" + marker,
                image_count=count,
                storage_used=0,
                status=Gallery.Status.DRAFT,
                visibility=Gallery.Visibility.PRIVATE,
            )])[0]
            GalleryPhoto.objects.bulk_create([
                GalleryPhoto(gallery_id=gallery.pk,
                             photographer_id=source.photographer_id,
                             file=originals[i % len(originals)],
                             original_name=f"benchmark-{i}.jpg",
                             file_size=0,
                             status=GalleryPhoto.Status.COMPLETED)
                for i in range(count)
            ], batch_size=500)
            factory = RequestFactory()
            last_page = (count + 59) // 60
            results = []
            for page_number in sorted({1, (last_page + 1) // 2, last_page}):
                request = factory.get("/", {"page": page_number})

                def run():
                    page, photos = _paginate_client_gallery_photos(request, gallery)
                    _prepare_client_gallery_content(gallery, photos, [])
                    urls = [photo.thumbnail_url for photo in photos]
                    return page, urls

                run()
                times = []
                for _ in range(iterations):
                    start = time.perf_counter()
                    page, urls = run()
                    times.append((time.perf_counter() - start) * 1000)
                with CaptureQueriesContext(connection) as queries:
                    run()
                tracemalloc.start()
                try:
                    run()
                    _, peak = tracemalloc.get_traced_memory()
                finally:
                    tracemalloc.stop()
                results.append({
                    "page": page_number, "photos": len(urls),
                    "median_ms": round(statistics.median(times), 2),
                    "max_ms": round(max(times), 2),
                    "queries": len(queries),
                    "python_peak_kib": round(peak / 1024, 2),
                })
            transaction.set_rollback(True)
        self.stdout.write(json.dumps({
            "synthetic_photos": count, "iterations": iterations,
            "scope": "client pagination, presentation metadata and signed thumbnail URLs",
            "persisted": False, "results": results,
        }, indent=2))
