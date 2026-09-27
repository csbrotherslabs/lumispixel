# Generated for LP-AUD-001 to make GalleryPhoto storage migration state portable.

import apps.galleries.models
import django.core.files.storage
import django.core.validators
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("galleries", "0010_gallery_assigned_members"),
    ]

    operations = [
        migrations.AlterField(
            model_name="galleryphoto",
            name="file",
            field=models.ImageField(
                storage=django.core.files.storage.FileSystemStorage(
                    location=settings.PRIVATE_MEDIA_ROOT
                ),
                upload_to=apps.galleries.models.gallery_photo_path,
                validators=[
                    django.core.validators.FileExtensionValidator(
                        ["jpg", "jpeg", "png", "webp"]
                    )
                ],
            ),
        ),
    ]
