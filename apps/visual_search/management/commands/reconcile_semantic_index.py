from django.core.management.base import BaseCommand
from apps.visual_search.models import SemanticIndexJob, GallerySemanticSearchPolicy
from apps.visual_search.semantic_tasks import index_semantic_gallery, dispatch_semantic_job

class Command(BaseCommand):
    help="Recover semantic indexing after broker interruptions or queryset-level upload completion."
    def add_arguments(self,parser):
        parser.add_argument("--limit",type=int,default=100)
    def handle(self,*args,**options):
        limit=max(0,min(options["limit"],1000))
        for gallery_id in GallerySemanticSearchPolicy.objects.filter(processing_authorized=True).values_list("gallery_id",flat=True)[:limit]:
            index_semantic_gallery(gallery_id)
        ids=SemanticIndexJob.objects.filter(status__in=["pending","failed","processing"]).order_by("created_at").values_list("pk",flat=True)[:limit]
        for pk in ids:
            dispatch_semantic_job(pk)
        self.stdout.write(self.style.SUCCESS("Semantic reconciliation dispatched."))
