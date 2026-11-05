from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("visual_search", "0004_private_gallery_access_requests"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ClientSelfieSearchPermission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("purpose", models.CharField(default="public_gallery_selfie_search", max_length=40)),
                ("policy_version", models.CharField(max_length=40)),
                ("granted_at", models.DateTimeField()),
                ("withdrawn_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="selfie_search_permissions", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["user", "purpose", "withdrawn_at"], name="visual_client_permission"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=["user", "purpose"],
                        condition=Q(withdrawn_at__isnull=True),
                        name="visual_one_active_client_selfie_permission",
                    ),
                ],
            },
        ),
    ]
