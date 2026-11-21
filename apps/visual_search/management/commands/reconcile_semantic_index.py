"""Recover semantic indexing jobs left behind by broker/worker interruptions."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.visual_search.models import SemanticIndexJob
from apps.visual_search.semantic_tasks import dispatch_semantic_job


class Command(BaseCommand):
    help = "Redispatch aged pending/failed semantic jobs without touching processing jobs."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--min-age-minutes", type=int, default=10)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        limit = max(0, min(options["limit"], 1000))
        minutes = max(1, options["min_age_minutes"])
        cutoff = timezone.now() - timedelta(minutes=minutes)
        jobs = list(
            SemanticIndexJob.objects.filter(
                status__in=["pending", "failed"],
                created_at__lte=cutoff,
                photo__gallery__deleted_at__isnull=True,
                photo__gallery__archived_at__isnull=True,
                photo__gallery__semantic_search_policy__processing_authorized=True,
            )
            .order_by("created_at")
            .values_list("pk", flat=True)[:limit]
        )
        for pk in jobs:
            if not options["dry_run"]:
                dispatch_semantic_job(pk)
        self.stdout.write(
            f"Semantic reconciliation: {len(jobs)} eligible job(s) "
            f"{'found (dry run)' if options['dry_run'] else 'dispatched'}."
        )
