from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies = [("notifications", "0010_email_intent")]
    operations = [
        migrations.AddField(model_name="emailattempt", name="transport", field=models.CharField(default="smtp", max_length=16)),
        migrations.AddField(model_name="emailattempt", name="provider_message_id", field=models.CharField(blank=True, db_index=True, max_length=255)),
    ]
