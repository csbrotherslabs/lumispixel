from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("galleries", "0028_galleryphotocomment"),
    ]

    operations = [
        migrations.AddField(
            model_name="gallery",
            name="design_template",
            field=models.CharField(
                choices=[("kimono_standard_filterable", "Standard Filterable")],
                default="kimono_standard_filterable",
                max_length=48,
            ),
        ),
    ]
