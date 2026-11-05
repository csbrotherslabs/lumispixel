from django.core.management.base import BaseCommand, CommandError
from apps.visual_search.vector_store import vector_connection


class Command(BaseCommand):
    help = "Purge all face embeddings for a photo ID in the isolated vector store."

    def add_arguments(self, parser):
        parser.add_argument("photo_id", type=int)

    def handle(self, *args, **options):
        photo_id = options["photo_id"]
        if photo_id <= 0:
            raise CommandError("photo_id must be positive")
        with vector_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM visual_search.app_face_embeddings WHERE photo_id = %s",
                (photo_id,),
            )
        self.stdout.write(f"Purged embeddings for photo {photo_id}: {cursor.rowcount} rows.")
