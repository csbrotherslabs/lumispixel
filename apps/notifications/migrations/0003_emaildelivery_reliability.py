from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("notifications", "0002_emaildelivery")]

    operations = [
        migrations.AlterField(
            model_name="emaildelivery",
            name="status",
            field=models.CharField(choices=[("pending", "Pending"), ("retry", "Retry scheduled"), ("sent", "Sent"), ("dead", "Dead letter"), ("failed", "Failed")], db_index=True, default="pending", max_length=12),
        ),
        migrations.AddField(model_name="emaildelivery", name="failure_kind", field=models.CharField(blank=True, choices=[("", "None"), ("transient", "Transient"), ("permanent", "Permanent"), ("unknown", "Unknown")], default="", max_length=12)),
        migrations.AddField(model_name="emaildelivery", name="next_attempt_at", field=models.DateTimeField(blank=True, db_index=True, null=True)),
        migrations.AddField(model_name="emaildelivery", name="dead_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddIndex(model_name="emaildelivery", index=models.Index(fields=["status", "next_attempt_at"], name="email_delivery_retry")),
    ]
