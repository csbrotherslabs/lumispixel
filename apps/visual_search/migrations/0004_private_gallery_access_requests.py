from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("visual_search", "0003_discovery_consent_constraint"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("galleries", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PrivateGalleryInvitation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                ("expires_at", models.DateTimeField()),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ("gallery", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="private_access_invitations", to="galleries.gallery")),
            ],
        ),
        migrations.CreateModel(
            name="PrivateGalleryAccessRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("denied", "Denied")], default="pending", max_length=12)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("invitation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="requests", to="visual_search.privategalleryinvitation")),
                ("requester", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="private_gallery_access_requests", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("invitation", "requester"), name="private_access_one_request_per_invite"),
                ],
            },
        ),
    ]
