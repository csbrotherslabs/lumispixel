from django.db import migrations


OPERATIONS = [
    ("face_detection", "Face Detection"),
    ("face_clustering", "Face Clustering"),
    ("duplicate_detection", "Duplicate Detection"),
    ("blur_detection", "Blur Detection"),
    ("closed_eyes_detection", "Closed Eyes Detection"),
    ("image_quality_scoring", "Image Quality Scoring"),
    ("scene_recognition", "Scene Recognition"),
    ("object_detection", "Object Detection"),
    ("color_detection", "Color Detection"),
    ("keyword_generation", "Keyword Generation"),
    ("search_indexing", "Search Indexing"),
]


def seed_operations(apps, schema_editor):
    AIOperation = apps.get_model("billing", "AIOperation")
    for code, name in OPERATIONS:
        AIOperation.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "default_units": 1,
                "is_active": True,
                "metadata": {"billing_basis": "image"},
            },
        )


def unseed_operations(apps, schema_editor):
    AIOperation = apps.get_model("billing", "AIOperation")
    AIOperation.objects.filter(code__in=[code for code, _ in OPERATIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [("billing", "0004_ai_usage_ledger")]

    operations = [migrations.RunPython(seed_operations, unseed_operations)]
