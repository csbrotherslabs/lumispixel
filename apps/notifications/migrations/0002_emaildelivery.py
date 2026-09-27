from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("notifications", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="EmailDelivery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("idempotency_key", models.CharField(max_length=64, unique=True)),
                ("event_key", models.CharField(db_index=True, max_length=255)),
                ("subject", models.CharField(max_length=255)),
                ("plain_body", models.TextField()),
                ("html_body", models.TextField(blank=True)),
                ("recipients", models.JSONField(default=list)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed")], db_index=True, default="pending", max_length=12)),
                ("attempt_count", models.PositiveSmallIntegerField(default=0)),
                ("last_error", models.TextField(blank=True)),
                ("last_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ("created_at", "pk")},
        ),
        migrations.AddIndex(
            model_name="emaildelivery",
            index=models.Index(fields=["status", "created_at"], name="email_delivery_queue"),
        ),
    ]
