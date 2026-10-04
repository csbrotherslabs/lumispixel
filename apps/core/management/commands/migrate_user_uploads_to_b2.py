"""Copy persisted upload references to B2, retaining names and local originals."""
import hashlib
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.files import File
from django.db.models import FileField

from apps.core.upload_storage import UserUploadStorage


def digest(stream):
    result = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        result.update(chunk)
    return result.hexdigest()


class Command(BaseCommand):
    help = "Dry-run by default. Copy referenced non-gallery uploads to B2 without deleting local files."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--source-root", default=str(settings.MEDIA_ROOT))
        parser.add_argument("--private-source-root", default=str(settings.PRIVATE_MEDIA_ROOT))

    def handle(self, *args, **options):
        if options["apply"] and settings.USER_UPLOAD_STORAGE_BACKEND != "b2":
            raise CommandError("Enable USER_UPLOAD_STORAGE_BACKEND=b2 in this command's environment first.")
        destination = UserUploadStorage()
        missing = 0
        checked = 0
        seen = set()
        for model in apps.get_models():
            # Gallery originals already have their own B2 pipeline and migration.
            if model._meta.label_lower == "galleries.galleryphoto":
                continue
            for field in model._meta.fields:
                if not isinstance(field, FileField):
                    continue
                private_document = model._meta.label_lower == "clients.signedcontractdocument"
                root = Path(options["private_source_root"] if private_document else options["source_root"]).resolve()
                for name in model.objects.exclude(**{field.name: ""}).exclude(
                    **{f"{field.name}__isnull": True}
                ).values_list(field.name, flat=True).iterator(chunk_size=200):
                    identity = (str(root), name)
                    if identity in seen:
                        continue
                    seen.add(identity)
                    source = (root / name).resolve()
                    if not source.is_relative_to(root):
                        raise CommandError("A stored file reference escapes its source directory.")
                    if not source.is_file():
                        missing += 1
                        self.stderr.write(f"Missing: {model._meta.label}.{field.name}: {name}")
                        continue
                    if options["apply"]:
                        backend = destination.backend_for(name)
                        with source.open("rb") as stream:
                            expected = digest(stream)
                        if not backend.exists(name):
                            with source.open("rb") as stream:
                                saved = backend.save(name, File(stream))
                            if saved != name:
                                raise CommandError(f"Concurrent destination collision: {name}; rerun to verify.")
                        with backend.open(name, "rb") as stream:
                            if digest(stream) != expected:
                                raise CommandError(f"Destination content mismatch: {name}")
                    checked += 1
        self.stdout.write(f"{'Verified' if options['apply'] else 'Found'} {checked} files; missing {missing}. Local files retained.")
        if missing:
            raise CommandError("Restore/re-upload missing referenced files before completing the cutover.")
