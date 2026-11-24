from django.core.management.base import BaseCommand, CommandError
from apps.galleries.models import Gallery
from apps.galleries.tasks import generate_gallery_cover_derivatives


class Command(BaseCommand):
    help = "Queue responsive derivatives for existing gallery covers."

    def add_arguments(self, parser):
        parser.add_argument("--gallery-id", type=int)
        parser.add_argument("--after-id", type=int, default=0)
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        limit = options["limit"]
        if not 1 <= limit <= 1000:
            raise CommandError("Limit must be between 1 and 1000.")
        galleries = Gallery.objects.exclude(cover_image="").filter(
            pk__gt=options["after_id"], deleted_at__isnull=True
        ).order_by("pk")
        if options["gallery_id"] is not None:
            galleries = galleries.filter(pk=options["gallery_id"])
        count = 0
        last = options["after_id"]
        for gallery_id in galleries.values_list("pk", flat=True)[:limit]:
            generate_gallery_cover_derivatives.delay(gallery_id)
            count += 1
            last = gallery_id
        self.stdout.write(f"Queued {count} galleries; last ID: {last}")
