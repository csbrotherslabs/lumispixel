from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("notifications", "0008_encrypted_email_payload")]
    operations = [
        migrations.AddField(model_name="emaildelivery", name="attempt_limit", field=models.PositiveIntegerField(default=6)),
        migrations.CreateModel(name="EmailAttempt", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("number", models.PositiveIntegerField()), ("started_at", models.DateTimeField()),
            ("finished_at", models.DateTimeField(null=True)), ("outcome", models.CharField(default="sending", max_length=32)),
            ("error_code", models.CharField(blank=True, max_length=128)),
            ("delivery", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="attempt_history", to="notifications.emaildelivery")),
        ], options={"constraints": [models.UniqueConstraint(fields=("delivery", "number"), name="unique_email_attempt_number")]}),
        migrations.CreateModel(name="EmailRecoveryEvent", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("actor_id", models.CharField(max_length=128)), ("reason", models.CharField(max_length=500)),
            ("previous_attempt_limit", models.PositiveIntegerField()), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("delivery", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="notifications.emaildelivery")),
        ]),
    ]
