from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("internal_ops", "0004_support_ticket_attachment")]

    operations = [
        migrations.CreateModel(
            name="SystemAlert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=120, unique=True)),
                ("component", models.CharField(max_length=80)),
                ("severity", models.CharField(choices=[("info", "Info"), ("warning", "Warning"), ("critical", "Critical")], default="warning", max_length=16)),
                ("status", models.CharField(choices=[("open", "Open"), ("acknowledged", "Acknowledged"), ("resolved", "Resolved")], default="open", max_length=20)),
                ("title", models.CharField(max_length=180)),
                ("message", models.TextField(max_length=1200)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("first_seen_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
                ("acknowledged_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("acknowledged_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="acknowledged_system_alerts", to="internal_ops.employeeprofile")),
                ("resolved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="resolved_system_alerts", to="internal_ops.employeeprofile")),
            ],
            options={"ordering": ("-last_seen_at",)},
        ),
        migrations.AddIndex(model_name="systemalert", index=models.Index(fields=["status", "severity", "last_seen_at"], name="system_alert_state_idx")),
        migrations.AddIndex(model_name="systemalert", index=models.Index(fields=["component", "last_seen_at"], name="system_alert_comp_idx")),
    ]
