from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("clients", "0006_alter_clientactivity_event_type")]
    operations = [
        migrations.AddField(
            model_name="clientsession", name="duration_minutes",
            field=models.PositiveIntegerField(default=120),
        ),
    ]
