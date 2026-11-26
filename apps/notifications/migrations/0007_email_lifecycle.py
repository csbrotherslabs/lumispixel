from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("notifications", "0006_brevoemailevent")]
    operations = [
        migrations.AddField(model_name="emaildelivery", name="expires_at", field=models.DateTimeField(null=True, blank=True, db_index=True)),
        migrations.AddField(model_name="emaildelivery", name="lifecycle_kind", field=models.CharField(max_length=64, blank=True, default="")),
        migrations.AddField(model_name="emaildelivery", name="lifecycle_context", field=models.JSONField(default=dict, blank=True)),
        migrations.AddField(model_name="emaildelivery", name="sensitive", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="emaildelivery", name="payload_purged_at", field=models.DateTimeField(null=True, blank=True)),
        migrations.AlterField(model_name="emaildelivery", name="status", field=models.CharField(max_length=12, db_index=True, default="pending", choices=[
            ("pending","Pending"),("retry","Retry scheduled"),("sent","Sent"),("sending","Sending"),("uncertain","Outcome uncertain"),("cancelled","Cancelled"),("expired","Expired"),("dead","Dead letter"),("failed","Failed")])),
    ]
