from django.core.management.base import BaseCommand
from django.conf import settings

from apps.visual_search.models import FaceIndexJob
from apps.visual_search.services import dispatch_face_index_job


class Command(BaseCommand):
    help = "Redispatch pending face-index jobs after broker interruptions."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        if not settings.VISUAL_SEARCH_FACE_INDEXING_ENABLED:
            self.stdout.write("Face indexing disabled; no jobs dispatched.")
            return
        limit = max(0, min(options["limit"], 1000))
        ids = list(
            FaceIndexJob.objects.filter(status=FaceIndexJob.Status.PENDING)
            .order_by("created_at")
            .values_list("pk", flat=True)[:limit]
        )
        for job_id in ids:
            dispatch_face_index_job(job_id)
        self.stdout.write(f"Attempted dispatch for {len(ids)} pending jobs.")
