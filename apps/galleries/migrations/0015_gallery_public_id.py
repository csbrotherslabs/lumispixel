import uuid
from django.db import migrations, models


def populate_public_ids(apps, schema_editor):
    Gallery = apps.get_model("galleries", "Gallery")
    for gallery in Gallery.objects.filter(public_id__isnull=True).iterator():
        gallery.public_id = uuid.uuid4()
        gallery.save(update_fields=["public_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("galleries", "0014_galleryphoto_upload_queue_dismissed"),
    ]

    operations = [
        migrations.AddField(
            model_name="gallery",
            name="public_id",
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.RunPython(populate_public_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="gallery",
            name="public_id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
