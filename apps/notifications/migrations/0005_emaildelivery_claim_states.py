from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("notifications", "0004_notificationeventreceipt")]
    operations = [
        migrations.AlterField(
            model_name="emaildelivery", name="status",
            field=models.CharField(max_length=12, db_index=True, default="pending",
                choices=[("pending", "Pending"), ("retry", "Retry scheduled"),
                         ("sent", "Sent"), ("sending", "Sending"),
                         ("uncertain", "Outcome uncertain"), ("dead", "Dead letter"),
                         ("failed", "Failed")]),
        ),
    ]
