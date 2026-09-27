import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import AdministrativeRegion, Country, LocationDatasetImport, PhotographerProfile, User


class LocationImportTests(TestCase):
    def _dataset(self, directory):
        path = Path(directory) / "locations.json"
        path.write_text(json.dumps({
            "metadata": {"source": "test/locations", "revision": "abc123"},
            "countries": [{
                "source_id": 233,
                "name": "United States",
                "iso2": "US",
                "iso3": "USA",
                "regions": [{"source_id": 1456, "name": "California", "code": "US-CA", "type": "state"}],
            }],
        }), encoding="utf-8")
        return path

    def test_import_is_idempotent_and_records_revision(self):
        with TemporaryDirectory() as directory:
            dataset = self._dataset(directory)
            call_command("import_locations", file=dataset)
            call_command("import_locations", file=dataset)

        self.assertEqual(Country.objects.count(), 1)
        self.assertEqual(AdministrativeRegion.objects.count(), 1)
        self.assertEqual(LocationDatasetImport.objects.count(), 2)
        self.assertEqual(LocationDatasetImport.objects.first().revision, "abc123")

    def test_dry_run_rolls_back_changes(self):
        with TemporaryDirectory() as directory:
            call_command("import_locations", file=self._dataset(directory), dry_run=True)

        self.assertFalse(Country.objects.exists())
        self.assertFalse(LocationDatasetImport.objects.exists())

    def test_import_backfills_legacy_photographer_location(self):
        user = User.objects.create_user(email="legacy-location@example.com", password="pass12345")
        profile = PhotographerProfile.objects.create(user=user, slug="legacy-location", country="United States", state="CA")
        with TemporaryDirectory() as directory:
            call_command("import_locations", file=self._dataset(directory))

        profile.refresh_from_db()
        self.assertEqual(profile.country_record.iso2, "US")
        self.assertEqual(profile.administrative_region.code, "US-CA")

    def test_invalid_dataset_is_rejected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text('{"countries": []}', encoding="utf-8")
            with self.assertRaises(CommandError):
                call_command("import_locations", file=path)


class AdministrativeRegionApiTests(TestCase):
    def setUp(self):
        self.country = Country.objects.create(source_id=233, name="United States", iso2="US", iso3="USA")
        self.region = AdministrativeRegion.objects.create(source_id=1456, country=self.country, name="California", code="US-CA", region_type="state")

    def test_regions_can_be_loaded_by_country_id_or_iso_code(self):
        url = reverse("api:administrative-regions")
        for country_value in (str(self.country.pk), "us"):
            response = self.client.get(url, {"country": country_value})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["regions"], [{"id": self.region.pk, "name": "California", "code": "US-CA", "region_type": "state"}])

    def test_missing_and_unknown_countries_return_clear_errors(self):
        url = reverse("api:administrative-regions")
        self.assertEqual(self.client.get(url).status_code, 400)
        self.assertEqual(self.client.get(url, {"country": "ZZ"}).status_code, 404)
