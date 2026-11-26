import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("accounts", "0013_photographerwebsiteequipment")]
    operations = [
        migrations.CreateModel(
            name="AutomationJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(max_length=100)),
                ("event_key", models.CharField(max_length=255)),
                ("target_id", models.PositiveBigIntegerField()),
                ("status", models.CharField(choices=[("pending", "Pending"), ("retry", "Retry"), ("succeeded", "Succeeded"), ("failed", "Failed")], default="pending", max_length=16)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("max_attempts", models.PositiveIntegerField(default=5)),
                ("available_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("error_code", models.CharField(blank=True, max_length=100)),
                ("photographer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="accounts.photographerprofile")),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("photographer", "kind", "event_key"), name="platform_job_event_unique")], "indexes": [models.Index(fields=["status", "available_at"], name="platform_job_due_idx")]},
        ),
        migrations.CreateModel(
            name="AutomationAttempt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.PositiveIntegerField()),
                ("started_at", models.DateTimeField()),
                ("finished_at", models.DateTimeField()),
                ("outcome", models.CharField(max_length=16)),
                ("error_code", models.CharField(blank=True, max_length=100)),
                ("job", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="history", to="automation.automationjob")),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("job", "number"), name="platform_job_attempt_unique")]},
        ),
    ]
