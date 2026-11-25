from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("marketplace", "0001_initial"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AlterField(model_name="platformbooking", name="customer", field=models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.CASCADE, null=True, blank=True)),
        migrations.AddField(model_name="platformbooking", name="created_by", field=models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL, null=True, blank=True, related_name="initiated_platform_bookings")),
        migrations.AddField(model_name="platformbooking", name="origin", field=models.CharField(max_length=20, default="client")),
        migrations.AddField(model_name="platformbooking", name="client_email", field=models.EmailField(max_length=254, blank=True)),
        migrations.AddField(model_name="platformbooking", name="verification_digest", field=models.CharField(max_length=64, blank=True, db_index=True)),
        migrations.AddField(model_name="platformbooking", name="verification_expires_at", field=models.DateTimeField(null=True, blank=True)),
        migrations.AddField(model_name="platformbooking", name="acknowledged_at", field=models.DateTimeField(null=True, blank=True)),
    ]
