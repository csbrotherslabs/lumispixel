from django.db import migrations, models
import django.db.models.deletion


def quarantine_legacy(apps, schema_editor):
    Delivery = apps.get_model("notifications", "EmailDelivery")
    from django.utils import timezone
    rows = Delivery.objects.filter(sensitive=True)
    rows.filter(status__in=["pending", "retry"]).update(status="cancelled", last_error="LegacySensitivePayload", next_attempt_at=None)
    rows.update(subject="[redacted]", plain_body="", html_body="", lifecycle_context={}, payload_purged_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [("notifications", "0007_email_lifecycle")]
    operations = [
        migrations.AddField(model_name="emaildelivery", name="encrypted_payload", field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="emaildelivery", name="supersession_scope", field=models.CharField(max_length=64, blank=True, default="", db_index=True)),
        migrations.CreateModel(name="EmailSupersession", fields=[
            ("scope", models.CharField(max_length=64, primary_key=True, serialize=False)),
            ("current", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to="notifications.emaildelivery")),
        ]),
        migrations.RunPython(quarantine_legacy, migrations.RunPython.noop),
    ]
