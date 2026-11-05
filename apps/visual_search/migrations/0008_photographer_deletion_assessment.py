from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("visual_search", "0007_face_deletion_review"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PhotographerDeletionAssessment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("outcome", models.CharField(max_length=24, choices=[("unverified", "Identity could not be verified"), ("reviewed", "Review completed for this gallery")])),
                ("reviewed_at", models.DateTimeField(auto_now=True)),
                ("request", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="photographer_assessments", to="visual_search.clientbiometricdeletionrequest")),
                ("gallery", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="galleries.gallery")),
                ("photographer_user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="biometric_deletion_assessments", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=["request", "gallery"], name="visual_unique_gallery_deletion_assessment")],
            },
        ),
    ]
