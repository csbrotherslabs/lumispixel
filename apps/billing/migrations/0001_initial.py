import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0013_photographerwebsiteequipment"),
    ]

    operations = [
        migrations.CreateModel(
            name="Plan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(max_length=40, unique=True)),
                ("name", models.CharField(max_length=80)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("is_public", models.BooleanField(default=True)),
                ("customer_selectable", models.BooleanField(default=False, help_text="Whether a photographer may self-select this plan. Paid plans stay disabled until launch readiness.")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["sort_order", "pk"]},
        ),
        migrations.CreateModel(
            name="PlanAllowance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.SlugField(max_length=80)),
                ("label", models.CharField(max_length=120)),
                ("limit_type", models.CharField(choices=[("numeric", "Numeric"), ("unlimited", "Unlimited"), ("custom", "Custom")], default="numeric", max_length=12)),
                ("value", models.PositiveBigIntegerField(blank=True, null=True)),
                ("unit", models.CharField(blank=True, max_length=40)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="allowances", to="billing.plan")),
            ],
            options={"ordering": ["plan__sort_order", "key"]},
        ),
        migrations.CreateModel(
            name="PlanEntitlement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(max_length=100)),
                ("label", models.CharField(max_length=140)),
                ("enabled", models.BooleanField(default=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="entitlements", to="billing.plan")),
            ],
            options={"ordering": ["plan__sort_order", "code"]},
        ),
        migrations.CreateModel(
            name="PlanPrice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("billing_interval", models.CharField(choices=[("monthly", "Monthly"), ("annual", "Annual"), ("custom", "Custom")], max_length=12)),
                ("amount_cents", models.PositiveIntegerField(blank=True, null=True)),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("is_active", models.BooleanField(default=True)),
                ("checkout_enabled", models.BooleanField(default=False, help_text="Keep disabled until a payment provider and checkout flow are ready.")),
                ("provider_product_id", models.CharField(blank=True, max_length=255)),
                ("provider_price_id", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="prices", to="billing.plan")),
            ],
            options={"ordering": ["plan__sort_order", "billing_interval"]},
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("active", "Active"), ("inactive", "Inactive"), ("past_due", "Past due"), ("canceled", "Canceled"), ("incomplete", "Incomplete")], default="active", max_length=16)),
                ("billing_interval", models.CharField(choices=[("free", "Free"), ("monthly", "Monthly"), ("annual", "Annual"), ("custom", "Custom")], default="free", max_length=12)),
                ("provider", models.CharField(choices=[("none", "None"), ("stripe", "Stripe")], default="none", max_length=12)),
                ("provider_customer_id", models.CharField(blank=True, max_length=255)),
                ("provider_subscription_id", models.CharField(blank=True, max_length=255)),
                ("current_period_start", models.DateTimeField(blank=True, null=True)),
                ("current_period_end", models.DateTimeField(blank=True, null=True)),
                ("cancel_at_period_end", models.BooleanField(default=False)),
                ("started_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("photographer", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="billing_subscription", to="accounts.photographerprofile")),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="subscriptions", to="billing.plan")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="planallowance",
            constraint=models.UniqueConstraint(fields=("plan", "key"), name="billing_plan_allowance_unique"),
        ),
        migrations.AddConstraint(
            model_name="planentitlement",
            constraint=models.UniqueConstraint(fields=("plan", "code"), name="billing_plan_entitlement_unique"),
        ),
        migrations.AddConstraint(
            model_name="planprice",
            constraint=models.UniqueConstraint(fields=("plan", "billing_interval", "currency"), name="billing_plan_interval_currency_unique"),
        ),
        migrations.AddIndex(
            model_name="subscription",
            index=models.Index(fields=["plan", "status"], name="billing_sub_plan_status"),
        ),
        migrations.AddIndex(
            model_name="subscription",
            index=models.Index(fields=["provider", "provider_subscription_id"], name="billing_sub_provider_id"),
        ),
    ]
