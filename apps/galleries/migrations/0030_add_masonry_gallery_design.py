from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("galleries", "0029_gallery_design_template"),
    ]

    operations = [
        migrations.AlterField(
            model_name="gallery",
            name="design_template",
            field=models.CharField(
                choices=[
                    ("kimono_standard_filterable", "Standard Filterable"),
                    ("kimono_masonry", "Masonry"),
                ],
                default="kimono_standard_filterable",
                max_length=48,
            ),
        ),
    ]
