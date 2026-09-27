from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0003_expand_higher_plan_entitlements"),
    ]

    operations = [
        migrations.CreateModel(
            name="AIOperation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(max_length=80, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("default_units", models.PositiveIntegerField(default=1)),
                ("is_active", models.BooleanField(default=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name", "pk"]},
        ),
        migrations.CreateModel(
            name="AIUsageAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("purchased_balance", models.PositiveBigIntegerField(default=0, help_text="Persistent purchased AI units. Phase 6 will add funded top-ups to this balance.")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("photographer", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="ai_usage_account", to="accounts.photographerprofile")),
            ],
        ),
        migrations.CreateModel(
            name="AIUsagePeriod",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("starts_at", models.DateTimeField()),
                ("ends_at", models.DateTimeField()),
                ("included_allowance", models.PositiveBigIntegerField(blank=True, null=True)),
                ("allowance_limit_type", models.CharField(choices=[("numeric", "Numeric"), ("unlimited", "Unlimited"), ("custom", "Custom")], default="numeric", max_length=12)),
                ("included_consumed", models.PositiveBigIntegerField(default=0)),
                ("included_reserved", models.PositiveBigIntegerField(default=0)),
                ("purchased_reserved", models.PositiveBigIntegerField(default=0)),
                ("plan_code_snapshot", models.SlugField(max_length=40)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="periods", to="billing.aiusageaccount")),
            ],
            options={"ordering": ["-starts_at"]},
        ),
        migrations.CreateModel(
            name="AIUsageTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("reserve", "Reserve"), ("settle", "Settle"), ("release", "Release"), ("reverse", "Reverse"), ("purchase_grant", "Purchase grant"), ("adjustment", "Adjustment")], max_length=20)),
                ("included_units", models.PositiveBigIntegerField(default=0)),
                ("purchased_units", models.PositiveBigIntegerField(default=0)),
                ("idempotency_key", models.CharField(max_length=160, unique=True)),
                ("source_reference", models.CharField(blank=True, max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="transactions", to="billing.aiusageaccount")),
                ("operation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="transactions", to="billing.aioperation")),
                ("period", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="transactions", to="billing.aiusageperiod")),
                ("related_transaction", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="follow_up_transactions", to="billing.aiusagetransaction")),
            ],
            options={"ordering": ["-created_at", "-pk"]},
        ),
        migrations.AddConstraint(
            model_name="aiusageperiod",
            constraint=models.UniqueConstraint(fields=("account", "starts_at"), name="ai_period_acct_start_uq"),
        ),
        migrations.AddIndex(
            model_name="aiusageperiod",
            index=models.Index(fields=["account", "starts_at", "ends_at"], name="ai_period_lookup_idx"),
        ),
        migrations.AddIndex(
            model_name="aiusagetransaction",
            index=models.Index(fields=["account", "created_at"], name="ai_tx_acct_time_idx"),
        ),
        migrations.AddIndex(
            model_name="aiusagetransaction",
            index=models.Index(fields=["kind", "created_at"], name="ai_tx_kind_time_idx"),
        ),
        migrations.AddIndex(
            model_name="aiusagetransaction",
            index=models.Index(fields=["source_reference"], name="ai_tx_source_idx"),
        ),
        migrations.AddConstraint(
            model_name="aiusagetransaction",
            constraint=models.CheckConstraint(condition=models.Q(("included_units__gt", 0), ("purchased_units__gt", 0), _connector="OR"), name="ai_tx_nonzero_ck"),
        ),
    ]
