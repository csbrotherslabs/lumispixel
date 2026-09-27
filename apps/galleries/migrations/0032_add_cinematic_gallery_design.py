from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("galleries", "0031_add_story_gallery_design")]
    operations = [migrations.AlterField(model_name="gallery", name="design_template", field=models.CharField(choices=[("kimono_standard_filterable", "Standard Filterable"), ("kimono_story", "Story"), ("kimono_masonry", "Masonry"), ("cinematic", "Cinematic")], default="kimono_standard_filterable", max_length=48))]
