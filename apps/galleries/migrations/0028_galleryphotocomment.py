from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("galleries", "0015_gallery_public_id"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GalleryPhotoComment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.TextField(max_length=2000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("author", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="gallery_photo_comments", to=settings.AUTH_USER_MODEL)),
                ("gallery", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="photo_comments", to="galleries.gallery")),
                ("invitation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="photo_comments", to="galleries.galleryinvitation")),
                ("photo", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="client_comments", to="galleries.galleryphoto")),
            ],
            options={"ordering": ["created_at", "pk"]},
        ),
    ]
