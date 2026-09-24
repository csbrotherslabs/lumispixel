from django.db import migrations


GIB = 1024 ** 3


def refresh_paid_plan_pricing(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    PlanPrice = apps.get_model("billing", "PlanPrice")
    PlanAllowance = apps.get_model("billing", "PlanAllowance")

    updates = {
        "pro": {
            "monthly": 2000,
            "annual": 19200,
            "storage_bytes": 1024 * GIB,
        },
        "studio": {
            "monthly": 3800,
            "annual": 36000,
            "storage_bytes": 4096 * GIB,
        },
    }

    for code, values in updates.items():
        plan = Plan.objects.get(code=code)
        PlanPrice.objects.update_or_create(
            plan=plan,
            billing_interval="monthly",
            currency="USD",
            defaults={"amount_cents": values["monthly"], "is_active": True, "checkout_enabled": False},
        )
        PlanPrice.objects.update_or_create(
            plan=plan,
            billing_interval="annual",
            currency="USD",
            defaults={"amount_cents": values["annual"], "is_active": True, "checkout_enabled": False},
        )
        PlanAllowance.objects.filter(plan=plan, key="storage_bytes").update(
            limit_type="numeric", value=values["storage_bytes"], unit="bytes"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0005_seed_processing_operations"),
    ]

    operations = [
        migrations.RunPython(refresh_paid_plan_pricing, migrations.RunPython.noop),
    ]
