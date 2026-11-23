"""Queue missing gallery derivatives in bounded batches.

Usage: python manage.py backfill_gallery_derivatives --gallery-id 1 --limit 100
"""
from django.core.management.base import BaseCommand
from apps.galleries.models import GalleryPhoto
from apps.galleries.derivatives import derivative_name
from apps.galleries.storage import gallery_photo_storage
from apps.galleries.tasks import generate_gallery_photo_derivatives


class Command(BaseCommand):
    help = "Enqueue missing private B2 gallery thumbnail/preview derivatives."

    def add_arguments(self, parser):
        parser.add_argument("--gallery-id", type=int)
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--after-id", type=int, default=0)

    def handle(self, *args, **options):
        limit = options["limit"]
        if not 1 <= limit <= 1000:
            raise ValueError("--limit must be between 1 and 1000")
        queryset = GalleryPhoto.objects.filter(
            status=GalleryPhoto.Status.COMPLETED, pk__gt=options["after_id"]
        ).exclude(file="").order_by("pk")
        if options["gallery_id"]:
            queryset = queryset.filter(gallery_id=options["gallery_id"])
        storage = gallery_photo_storage()
        queued = 0
        last_id = options["after_id"]
        for photo in queryset.iterator(chunk_size=100):
            last_id = photo.pk
            if any(not storage.exists(derivative_name(photo.file.name, kind))
                   for kind in ("thumbnail", "preview")):
                generate_gallery_photo_derivatives.delay(photo.pk)
                queued += 1
            if queued >= limit:
                break
        self.stdout.write(f"Queued {queued} photo(s); last scanned photo ID: {last_id}. "
                          f"Resume with --after-id {last_id}.")
