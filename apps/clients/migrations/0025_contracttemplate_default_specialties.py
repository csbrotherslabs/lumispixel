from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("clients", "0024_financial_integrity_constraints")]
    operations = [migrations.AddField(model_name="contracttemplate", name="default_specialties", field=models.JSONField(blank=True, default=list))]
