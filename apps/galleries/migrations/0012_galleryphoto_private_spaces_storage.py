import apps.galleries.models
import apps.galleries.storage
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("galleries", "0011_alter_galleryphoto_file"),
    ]

    operations = [
        migrations.AlterField(
            model_name="galleryphoto",
            name="file",
            field=models.ImageField(
                storage=apps.galleries.storage.gallery_photo_storage,
                upload_to=apps.galleries.models.gallery_photo_path,
                validators=[
                    django.core.validators.FileExtensionValidator(
                        ["jpg", "jpeg", "png", "webp"]
                    )
                ],
            ),
        ),
    ]
