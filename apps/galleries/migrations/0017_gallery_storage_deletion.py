from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("galleries", "0016_gallery_activity"),
    ]

    operations = [
        migrations.CreateModel(
            name="GalleryStorageDeletion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("storage_backend", models.CharField(choices=[("b2", "Backblaze B2"), ("default", "Default storage")], max_length=20)),
                ("object_key", models.CharField(max_length=700)),
                ("photographer_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("gallery_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("last_error", models.CharField(blank=True, max_length=1000)),
                ("last_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "indexes": [models.Index(fields=["completed_at", "created_at"], name="gallery_storage_delete_pending")],
                "constraints": [models.UniqueConstraint(fields=("storage_backend", "object_key"), name="gallery_storage_delete_object_unique")],
            },
        ),
    ]
