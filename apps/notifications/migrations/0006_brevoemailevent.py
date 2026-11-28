from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("notifications", "0005_emaildelivery_claim_states")]
    operations = [
        migrations.CreateModel(name="BrevoEmailEvent", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("fingerprint", models.CharField(max_length=64, unique=True)),
            ("event", models.CharField(max_length=32, db_index=True)),
            ("provider_message_id", models.CharField(max_length=255)),
            ("recipient_hash", models.CharField(max_length=64)),
            ("occurred_at", models.PositiveBigIntegerField()),
            ("received_at", models.DateTimeField(auto_now_add=True)),
            ("delivery", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="brevo_events", to="notifications.emaildelivery")),
        ]),
    ]
