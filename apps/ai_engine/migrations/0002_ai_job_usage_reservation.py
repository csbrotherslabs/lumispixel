from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0005_seed_processing_operations"),
        ("ai_engine", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="aijob",
            name="usage_reservation",
            field=models.ForeignKey(
                blank=True,
                help_text="Current-attempt AI usage reservation. Historical ledger rows remain append-only.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ai_jobs",
                to="billing.aiusagetransaction",
            ),
        ),
    ]
