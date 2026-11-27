from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from apps.notifications.recovery import requeue_dead

class Command(BaseCommand):
    help = "Audited requeue of eligible non-sensitive dead letters; scanner dispatches them."
    def add_arguments(self, parser):
        parser.add_argument("--id", type=int, action="append", dest="ids", required=True)
        parser.add_argument("--actor-id", required=True)
        parser.add_argument("--reason", required=True)

    def handle(self, *args, **options):
        user = get_user_model().objects.filter(pk=options["actor_id"], is_active=True, is_superuser=True).first()
        if not user:
            raise CommandError("Active superuser required.")
        for pk in options["ids"]:
            try:
                requeue_dead(delivery_id=pk, user=user, reason=options["reason"])
            except ValidationError as exc:
                self.stderr.write(f"Delivery {pk}: {exc.messages[0]}")
            else:
                self.stdout.write(f"Delivery {pk} queued for recovery.")
