from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("clients", "0025_contracttemplate_default_specialties")]
    operations = [
        migrations.AddField(model_name="clientsession", name="pricing_confirmed", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="clientsession", name="payment_currency", field=models.CharField(max_length=3, blank=True)),
        migrations.AddField(model_name="clientsession", name="deposit_amount", field=models.DecimalField(max_digits=12, decimal_places=2, default=0)),
        migrations.AddField(model_name="clientsession", name="deposit_due_date", field=models.DateField(null=True, blank=True)),
        migrations.AddField(model_name="clientsession", name="balance_due_date", field=models.DateField(null=True, blank=True)),
    ]
