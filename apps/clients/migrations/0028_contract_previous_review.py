from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("clients", "0027_confirm_fully_signed_bookings")]
    operations = [
        migrations.AddField(model_name="contract", name="previous_review_digest", field=models.CharField(max_length=64, blank=True, default="", db_index=True, editable=False)),
        migrations.AddField(model_name="contract", name="previous_review_expires_at", field=models.DateTimeField(null=True, blank=True)),
    ]
