from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("dashboard", "0007_scheduleconstraint")]
    operations = [
        migrations.AddField(model_name="studiomembership", name="previous_invitation_digest", field=models.CharField(max_length=64, blank=True, default="", editable=False, db_index=True)),
        migrations.AddField(model_name="studiomembership", name="previous_invitation_expires_at", field=models.DateTimeField(null=True, blank=True)),
    ]
