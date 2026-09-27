from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("galleries", "0030_add_masonry_gallery_design"),
    ]

    operations = [
        migrations.AddField(
            model_name="gallery",
            name="story_title",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="gallery",
            name="story_description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="gallery",
            name="story_quote",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="gallery",
            name="design_template",
            field=models.CharField(
                choices=[
                    ("kimono_standard_filterable", "Standard Filterable"),
                    ("kimono_story", "Story"),
                    ("kimono_masonry", "Masonry"),
                ],
                default="kimono_standard_filterable",
                max_length=48,
            ),
        ),
    ]
