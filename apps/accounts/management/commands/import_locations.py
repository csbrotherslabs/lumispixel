import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import AdministrativeRegion, Country, LocationDatasetImport, PhotographerProfile


DEFAULT_DATASET = Path(settings.BASE_DIR) / "data" / "locations" / "countries_regions.json"


class Command(BaseCommand):
    help = "Import LumisPixel's pinned country and administrative-region dataset."

    def add_arguments(self, parser):
        parser.add_argument("--file", type=Path, default=DEFAULT_DATASET, help="Path to a compatible JSON snapshot.")
        parser.add_argument("--dry-run", action="store_true", help="Validate and process the file, then roll back all database changes.")

    def handle(self, *args, **options):
        dataset_path = options["file"]
        if not dataset_path.is_file():
            raise CommandError(f"Location dataset not found: {dataset_path}")

        try:
            payload = json.loads(dataset_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Could not read location dataset: {exc}") from exc

        metadata = payload.get("metadata", {})
        countries = payload.get("countries")
        if not metadata.get("source") or not metadata.get("revision") or not isinstance(countries, list):
            raise CommandError("Dataset must include metadata.source, metadata.revision, and a countries list.")

        self._validate(countries)
        with transaction.atomic():
            country_count = 0
            region_count = 0
            for country_data in countries:
                country, _ = Country.objects.update_or_create(
                    iso2=country_data["iso2"],
                    defaults={
                        "source_id": country_data["source_id"],
                        "name": country_data["name"],
                        "iso3": country_data["iso3"],
                        "is_active": True,
                    },
                )
                country_count += 1
                for region_data in country_data["regions"]:
                    AdministrativeRegion.objects.update_or_create(
                        source_id=region_data["source_id"],
                        defaults={
                            "country": country,
                            "name": region_data["name"],
                            "code": region_data.get("code", ""),
                            "region_type": region_data.get("type", ""),
                            "is_active": True,
                        },
                    )
                    region_count += 1

            LocationDatasetImport.objects.create(
                source=metadata["source"],
                revision=metadata["revision"],
                country_count=country_count,
                region_count=region_count,
            )
            linked_profile_count = self._backfill_photographer_locations()
            if options["dry_run"]:
                transaction.set_rollback(True)

        suffix = " (dry run; changes rolled back)" if options["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(f"Processed {country_count} countries and {region_count} regions; linked {linked_profile_count} legacy photographer profiles{suffix}."))

    def _backfill_photographer_locations(self):
        linked_count = 0
        profiles = PhotographerProfile.objects.filter(country_record__isnull=True).exclude(country="")
        for profile in profiles.iterator():
            country = Country.objects.filter(name__iexact=profile.country, is_active=True).first()
            if country is None:
                continue
            region = None
            if profile.state:
                regions = country.administrative_regions.filter(is_active=True)
                region = regions.filter(name__iexact=profile.state).first()
                if region is None:
                    region = regions.filter(code__iexact=profile.state).first()
                if region is None:
                    region = regions.filter(code__iendswith=f"-{profile.state}").first()
            profile.country_record = country
            profile.administrative_region = region
            profile.save(update_fields=["country_record", "administrative_region", "updated_at"])
            linked_count += 1
        return linked_count

    def _validate(self, countries):
        country_ids = set()
        iso2_codes = set()
        iso3_codes = set()
        region_ids = set()
        for country in countries:
            required = ("source_id", "name", "iso2", "iso3", "regions")
            if any(key not in country for key in required):
                raise CommandError(f"Country record is missing one of: {', '.join(required)}")
            iso2 = country["iso2"].upper()
            iso3 = country["iso3"].upper()
            if len(iso2) != 2 or len(iso3) != 3:
                raise CommandError(f"Invalid ISO code for {country['name']}.")
            if country["source_id"] in country_ids or iso2 in iso2_codes or iso3 in iso3_codes:
                raise CommandError(f"Duplicate country identifier for {country['name']}.")
            country_ids.add(country["source_id"])
            iso2_codes.add(iso2)
            iso3_codes.add(iso3)
            for region in country["regions"]:
                if "source_id" not in region or not region.get("name"):
                    raise CommandError(f"Invalid region record for {country['name']}.")
                if region["source_id"] in region_ids:
                    raise CommandError(f"Duplicate region identifier for {country['name']}: {region['name']}")
                region_ids.add(region["source_id"])
