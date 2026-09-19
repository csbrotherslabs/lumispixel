import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("galleries", "0008_galleryactivity_actor_type_galleryactivity_description_and_more")]

    operations = [
        migrations.CreateModel(
            name="GalleryMultipartUpload",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("object_key", models.CharField(max_length=700, unique=True)),
                ("upload_id", models.TextField()),
                ("original_name", models.CharField(max_length=255)),
                ("content_type", models.CharField(max_length=100)),
                ("file_size", models.PositiveBigIntegerField()),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("aborted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("gallery", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="multipart_uploads", to="galleries.gallery")),
                ("photographer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="gallery_multipart_uploads", to="accounts.photographerprofile")),
            ],
        ),
    ]
