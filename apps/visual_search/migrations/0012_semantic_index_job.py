from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[("visual_search","0011_gallery_semantic_policy")]
    operations=[migrations.CreateModel(
        name="SemanticIndexJob",
        fields=[
            ("id",models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ("source_key",models.CharField(max_length=700)),
            ("model_version",models.CharField(max_length=80)),
            ("status",models.CharField(max_length=16,default="pending",choices=[("pending","Pending"),("processing","Processing"),("completed","Completed"),("failed","Failed"),("cancelled","Cancelled")])),
            ("created_at",models.DateTimeField(auto_now_add=True)),
            ("updated_at",models.DateTimeField(auto_now=True)),
            ("photo",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="semantic_index_jobs",to="galleries.galleryphoto")),
        ],
        options={"indexes":[models.Index(fields=["status","created_at"],name="visual_semantic_job_queue")],"constraints":[models.UniqueConstraint(fields=["photo","source_key","model_version"],name="visual_semantic_job_unique")]},
    )]
