from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[("visual_search","0010_deletion_scope_attestation")]
    operations=[migrations.CreateModel(
        name="GallerySemanticSearchPolicy",
        fields=[
            ("id",models.BigAutoField(primary_key=True,serialize=False)),
            ("processing_authorized",models.BooleanField(default=False)),
            ("authorized_at",models.DateTimeField(blank=True,null=True)),
            ("updated_at",models.DateTimeField(auto_now=True)),
            ("gallery",models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,related_name="semantic_search_policy",to="galleries.gallery")),
        ],
    )]
