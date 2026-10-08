from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("galleries", "0035_photo_comment_threads_and_reactions")]
    operations = [
        migrations.AlterField(
            model_name="galleryphotocomment",
            name="invitation",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="photo_comments", to="galleries.galleryinvitation"),
        ),
    ]
