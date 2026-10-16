from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):
    initial = True
    dependencies = [("galleries", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="GalleryFaceSearchPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("processing_authorized", models.BooleanField(default=False)),
                ("global_discovery_enabled", models.BooleanField(default=False)),
                ("authorized_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("gallery", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="face_search_policy", to="galleries.gallery")),
            ],
        ),
        migrations.CreateModel(
            name="FaceIndexJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_key", models.CharField(max_length=700)),
                ("source_version", models.PositiveIntegerField(default=1)),
                ("model_version", models.CharField(default="arcface-buffalo-l-v1", max_length=80)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("processing", "Processing"), ("completed", "Completed"), ("failed", "Failed"), ("cancelled", "Cancelled")], default="pending", max_length=16)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("photo", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="face_index_jobs", to="galleries.galleryphoto")),
            ],
            options={
                "indexes": [models.Index(fields=["status", "created_at"], name="visual_face_job_pending")],
                "constraints": [
                    models.UniqueConstraint(fields=["photo", "source_version", "model_version"], name="visual_face_job_unique_version"),
                    models.CheckConstraint(condition=Q(source_version__gte=1), name="visual_face_version_positive"),
                ],
            },
        ),
    ]
