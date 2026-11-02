from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('galleries', '0038_watermark_density')]
    operations = [migrations.AddField(model_name='gallery', name='cover_zoom',
        field=models.PositiveSmallIntegerField(default=100, validators=[MinValueValidator(100), MaxValueValidator(300)]))]
