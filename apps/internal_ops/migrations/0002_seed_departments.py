from django.db import migrations


DEPARTMENTS = (
    ("Human Resources", "human-resources", "Employee operations, people programs, policies, and organizational support."),
    ("Customer Support", "customer-support", "Customer assistance, ticket resolution, escalations, and service quality."),
    ("Engineering", "engineering", "Product engineering, platform development, infrastructure, and reliability."),
    ("AI Operations", "ai-operations", "AI processing operations, model/provider oversight, usage, quality, and exceptions."),
    ("Finance", "finance", "Financial operations, billing oversight, economics, forecasting, and controls."),
    ("Sales", "sales", "Customer acquisition, partnerships, pipeline, and commercial growth."),
    ("Marketing", "marketing", "Brand, campaigns, content, lifecycle marketing, and growth programs."),
    ("Photography Operations", "photography-operations", "Photographer operations, event coverage, field coordination, and service delivery."),
    ("Trust & Safety", "trust-safety", "Platform safety, abuse prevention, privacy operations, and policy enforcement."),
    ("Executive", "executive", "Company leadership, strategy, operating performance, and executive oversight."),
)


def seed_departments(apps, schema_editor):
    Department = apps.get_model("internal_ops", "Department")
    for name, code, description in DEPARTMENTS:
        Department.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": description, "is_active": True},
        )


def remove_seeded_departments(apps, schema_editor):
    Department = apps.get_model("internal_ops", "Department")
    Department.objects.filter(code__in=[item[1] for item in DEPARTMENTS]).delete()


class Migration(migrations.Migration):
    dependencies = [("internal_ops", "0001_initial")]

    operations = [migrations.RunPython(seed_departments, remove_seeded_departments)]
