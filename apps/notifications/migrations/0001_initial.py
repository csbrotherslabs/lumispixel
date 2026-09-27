from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("category", models.CharField(choices=[("gallery", "Gallery"), ("download", "Download"), ("payment", "Payment"), ("message", "Message"), ("security", "Security"), ("system", "System")], default="system", max_length=20)),
                ("title", models.CharField(max_length=160)),
                ("message", models.TextField(max_length=1000)),
                ("action_url", models.CharField(blank=True, max_length=500)),
                ("action_label", models.CharField(blank=True, max_length=60)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("is_read", models.BooleanField(default=False)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at", "-pk")},
        ),
        migrations.AddIndex(model_name="notification", index=models.Index(fields=["recipient", "is_read", "-created_at"], name="notify_rec_read_created")),
        migrations.AddIndex(model_name="notification", index=models.Index(fields=["recipient", "category", "-created_at"], name="notify_rec_cat_created")),
    ]
