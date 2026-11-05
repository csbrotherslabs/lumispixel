from django.db import migrations, models
from django.db.models import Q


def clear_unauthorized_discovery(apps, schema_editor):
    Policy = apps.get_model("visual_search", "GalleryFaceSearchPolicy")
    Policy.objects.using(schema_editor.connection.alias).filter(
        processing_authorized=False, global_discovery_enabled=True
    ).update(global_discovery_enabled=False)


class Migration(migrations.Migration):
    dependencies = [("visual_search", "0002_worker_fencing_and_purges")]

    operations = [
        migrations.RunPython(clear_unauthorized_discovery, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="galleryfacesearchpolicy",
            constraint=models.CheckConstraint(
                condition=Q(processing_authorized=True) | Q(global_discovery_enabled=False),
                name="visual_discovery_requires_consent",
            ),
        ),
    ]
