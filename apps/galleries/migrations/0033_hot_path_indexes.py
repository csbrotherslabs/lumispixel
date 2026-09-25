from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("galleries", "0017_gallery_storage_deletion")]

    operations = [
        migrations.AddIndex(model_name="gallery", index=models.Index(fields=["photographer", "deleted_at", "archived_at", "-created_at"], name="gallery_owner_active_date")),
        migrations.AddIndex(model_name="galleryphoto", index=models.Index(fields=["gallery", "status", "is_visible", "-created_at"], name="photo_gallery_visible_date")),
        migrations.AddIndex(model_name="gallerymultipartupload", index=models.Index(fields=["completed_at", "aborted_at", "created_at"], name="multipart_active_created")),
        migrations.AddIndex(model_name="gallerymultipartupload", index=models.Index(fields=["photographer", "gallery", "completed_at", "aborted_at"], name="multipart_owner_gallery")),
    ]
