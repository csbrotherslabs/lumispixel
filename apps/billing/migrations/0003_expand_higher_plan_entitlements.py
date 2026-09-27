from django.db import migrations


PLAN_CHAIN = [
    ("free", "pro"),
    ("pro", "studio"),
    ("studio", "enterprise"),
]


def expand_entitlements(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    PlanEntitlement = apps.get_model("billing", "PlanEntitlement")

    for source_code, target_code in PLAN_CHAIN:
        source = Plan.objects.get(code=source_code)
        target = Plan.objects.get(code=target_code)
        for entitlement in PlanEntitlement.objects.filter(plan=source, enabled=True):
            PlanEntitlement.objects.get_or_create(
                plan=target,
                code=entitlement.code,
                defaults={
                    "label": entitlement.label,
                    "enabled": True,
                    "metadata": entitlement.metadata,
                },
            )


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0002_seed_launch_plans"),
    ]

    operations = [
        migrations.RunPython(expand_entitlements, migrations.RunPython.noop),
    ]
