from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("visual_search", "0006_client_biometric_deletion_request"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("galleries", "__latest__"),
    ]

    operations = [
        migrations.CreateModel(
            name="FaceDeletionReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("face_index", models.PositiveIntegerField()),
                ("confirmed_at", models.DateTimeField(auto_now_add=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                ("request", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="face_reviews", to="visual_search.clientbiometricdeletionrequest")),
                ("gallery", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="galleries.gallery")),
                ("photo", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="galleries.galleryphoto")),
                ("confirmed_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="confirmed_face_deletions", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [models.Index(fields=["photo", "deleted_at"], name="visual_face_erasure_photo")],
                "constraints": [models.UniqueConstraint(fields=["request", "photo", "face_index"], name="visual_unique_face_deletion_review")],
            },
        ),
    ]
