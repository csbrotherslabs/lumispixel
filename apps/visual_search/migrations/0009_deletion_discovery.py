from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("visual_search", "0008_photographer_deletion_assessment"),
    ]

    operations = [
        migrations.AddField(
            model_name="facedeletionreview", name="face_id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AddField(
            model_name="facedeletionreview", name="source_version",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="facedeletionreview", name="model_version",
            field=models.CharField(max_length=80, blank=True),
        ),
        migrations.CreateModel(
            name="BiometricDeletionDiscoveryGrant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("policy_version", models.CharField(max_length=40)),
                ("authorized_at", models.DateTimeField()),
                ("withdrawn_at", models.DateTimeField(blank=True, null=True)),
                ("request", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="discovery_grant", to="visual_search.clientbiometricdeletionrequest")),
            ],
        ),
        migrations.CreateModel(
            name="BiometricDeletionDiscoveryCandidate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(max_length=20, default="pending", choices=[("pending", "Pending photographer review"), ("unverified", "Unable to verify"), ("reviewed", "Reviewed")])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("request", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="discovery_candidates", to="visual_search.clientbiometricdeletionrequest")),
                ("gallery", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="galleries.gallery")),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=["request", "gallery"], name="visual_unique_erasure_candidate")],
            },
        ),
    ]
