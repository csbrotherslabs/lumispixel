from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("galleries", "0009_gallerymultipartupload"),
    ]

    operations = [
        migrations.AddField(
            model_name="galleryphoto",
            name="upload_queue_dismissed",
            field=models.BooleanField(default=False),
        ),
    ]
