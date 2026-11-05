from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("visual_search", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="faceindexjob", name="claim_token",
            field=models.UUIDField(blank=True, editable=False, null=True),
        ),
        migrations.CreateModel(
            name="FaceVectorPurge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("photo", "Photo"), ("gallery", "Gallery")], max_length=10)),
                ("object_id", models.BigIntegerField()),
                ("status", models.CharField(choices=[("pending", "Pending"), ("processing", "Processing"), ("completed", "Completed")], default="pending", max_length=12)),
                ("claim_token", models.UUIDField(blank=True, null=True)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("last_error", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"indexes": [models.Index(fields=["status", "created_at"], name="visual_purge_pending")]},
        ),
    ]
