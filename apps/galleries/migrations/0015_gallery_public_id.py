import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("galleries", "0014_galleryphoto_upload_queue_dismissed"),
    ]

    operations = [
        migrations.AddField(
            model_name="gallery",
            name="public_id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
