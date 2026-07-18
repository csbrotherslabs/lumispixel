from django.db import migrations
from django.utils.text import slugify


SPECIALTIES = [
    "Wedding",
    "Portrait",
    "Family",
    "Sports",
    "School",
    "Event",
    "Corporate",
    "Commercial",
    "Product",
    "Real Estate",
    "Street",
    "Fashion",
    "Nature",
    "Other",
]


def seed_photographer_specialties(apps, schema_editor):
    PhotographerSpecialty = apps.get_model("accounts", "PhotographerSpecialty")
    for name in SPECIALTIES:
        PhotographerSpecialty.objects.update_or_create(
            slug=slugify(name),
            defaults={"name": name, "is_active": True},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_remove_photographerprofile_profile_image_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_photographer_specialties, migrations.RunPython.noop),
    ]
