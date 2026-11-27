from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("notifications", "0009_email_attempt_history")]
    operations = [
        migrations.CreateModel(name="EmailIntent", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("key", models.CharField(max_length=64, unique=True)),
            ("event_key", models.CharField(max_length=255, db_index=True)),
            ("kind", models.CharField(max_length=64, blank=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("cancelled_at", models.DateTimeField(null=True, blank=True)),
            ("cancellation_reason", models.CharField(max_length=500, blank=True)),
            ("cancelled_by", models.CharField(max_length=128, blank=True)),
            ("delivery", models.OneToOneField(null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, related_name="intent", to="notifications.emaildelivery")),
        ]),
    ]
