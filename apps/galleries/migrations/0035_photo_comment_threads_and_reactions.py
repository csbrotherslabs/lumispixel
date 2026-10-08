from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("galleries", "0034_galleryphoto_multipart_upload"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField(
            model_name="galleryphotocomment",
            name="parent",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="replies", to="galleries.galleryphotocomment"),
        ),
        migrations.CreateModel(
            name="GalleryPhotoCommentReaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("value", models.SmallIntegerField(choices=[(1, "Like"), (-1, "Dislike")])),
                ("comment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reactions", to="galleries.galleryphotocomment")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="photo_comment_reactions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"constraints": [
                models.UniqueConstraint(fields=("comment", "user"), name="photo_comment_user_reaction"),
                models.CheckConstraint(condition=models.Q(value__in=[-1, 1]), name="photo_comment_reaction_value"),
            ]},
        ),
    ]
