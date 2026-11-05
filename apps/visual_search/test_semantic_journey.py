"""Semantic lifecycle contracts. Real model/vector tests are explicitly opt-in."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, mock_open

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from apps.accounts.models import PhotographerProfile
from apps.galleries.models import Gallery, GalleryPhoto, GalleryPermission
from .models import GallerySemanticSearchPolicy, SemanticIndexJob
from .semantic_tasks import index_semantic_photo, purge_semantic_gallery, schedule_semantic_photo


@override_settings(VISUAL_SEARCH_SEMANTIC_ENABLED=True, VISUAL_SEARCH_SEMANTIC_POLICY_APPROVED=True)
class SemanticJourneyTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(email="semantic@example.test", password="test", primary_role="photographer", email_verified=True)
        self.profile = PhotographerProfile.objects.create(user=self.owner, slug="semantic-test", onboarding_completed=True)
        self.gallery = Gallery.objects.create(photographer=self.profile, name="Search test", slug="search-test", status=Gallery.Status.PUBLISHED, visibility=Gallery.Visibility.PUBLIC)
        self.policy = GallerySemanticSearchPolicy.objects.create(gallery=self.gallery, processing_authorized=True)
        self.photo = GalleryPhoto.objects.create(gallery=self.gallery, photographer=self.profile, file="test.jpg", status=GalleryPhoto.Status.COMPLETED)
        self.url = reverse("visual_search:ai-discovery-settings", args=[self.gallery.pk])
        self.client.force_login(self.owner)

    def test_enable_disable_reenable_queues_and_reindexes(self):
        job = SemanticIndexJob.objects.get(photo=self.photo)
        job.status = "completed"
        job.save()
        with patch("apps.visual_search.semantic_tasks.purge_semantic_gallery.delay") as purge:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(self.url, json.dumps({"semantic_enabled": False}), content_type="application/json")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(purge.called)
        with patch("apps.visual_search.semantic_tasks.index_semantic_gallery.delay") as index:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(self.url, json.dumps({"semantic_enabled": True}), content_type="application/json")
            self.assertEqual(response.status_code, 200)
            index.assert_called_once_with(self.gallery.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, "pending")

    def test_delayed_purge_preserves_later_opt_in(self):
        with patch("apps.visual_search.semantic_tasks.purge_gallery") as purge:
            self.assertEqual(purge_semantic_gallery.run(self.gallery.pk), "reauthorized")
            purge.assert_not_called()

    def test_revocation_purges_semantic_only(self):
        self.policy.processing_authorized = False
        self.policy.save()
        with patch("apps.visual_search.semantic_tasks.purge_gallery") as purge, patch("apps.visual_search.vector_store.delete_gallery_embeddings") as face:
            self.assertEqual(purge_semantic_gallery.run(self.gallery.pk), "purged")
            purge.assert_called_once_with(self.gallery.pk)
            face.assert_not_called()
        self.assertEqual(SemanticIndexJob.objects.get(photo=self.photo).status, "cancelled")

    def test_other_owner_and_facial_mutation_rejected(self):
        self.assertEqual(self.client.post(self.url, json.dumps({"semantic_enabled": True, "facial_enabled": True}), content_type="application/json").status_code, 400)
        other = get_user_model().objects.create_user(email="other-semantic@example.test", password="test")
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.get(reverse("visual_search:semantic-search", args=[self.gallery.pk]), {"q": "cake"}).status_code, 404)

    def test_client_results_recheck_photo_visibility_and_gallery(self):
        GalleryPermission.objects.update_or_create(gallery=self.gallery, defaults={"view_gallery": True})
        self.photo.is_visible = False
        self.photo.save()
        with patch("apps.visual_search.semantic_api._semantic_results", return_value=[self.photo.pk]):
            response = self.client.get(reverse("visual_search:public-semantic-search", args=[self.gallery.public_id]), {"q": "cake"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])

    def test_create_page_has_two_submit_controls_and_opt_in_is_off(self):
        from html.parser import HTMLParser
        class Controls(HTMLParser):
            def __init__(self):
                super().__init__()
                self.submits = []
                self.semantic = None
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == "button" and "data-gallery-submit" in attrs:
                    self.submits.append(attrs)
                if attrs.get("id") == "lp-semantic-toggle":
                    self.semantic = attrs
        response = self.client.get(reverse("photographer_workspace:create_gallery"))
        self.assertEqual(response.status_code, 200)
        controls = Controls()
        controls.feed(response.content.decode())
        self.assertEqual(len(controls.submits), 2)
        self.assertTrue(all(button["type"] == "submit" for button in controls.submits))
        self.assertIsNotNone(controls.semantic)
        self.assertNotIn("checked", controls.semantic)

    def test_indexing_completes_and_is_idempotent(self):
        job = SemanticIndexJob.objects.get(photo=self.photo)
        with patch("django.db.models.fields.files.FieldFile.open", mock_open(read_data=b"photo")), patch("apps.visual_search.semantic_tasks.embed_image", return_value=[1.0] * 512), patch("apps.visual_search.semantic_tasks.replace_photo") as replace:
            self.assertEqual(index_semantic_photo.run(job.pk), "indexed")
            self.assertEqual(index_semantic_photo.run(job.pk), "already_completed")
            replace.assert_called_once()
        job.refresh_from_db()
        self.assertEqual(job.status, "completed")

    def test_deletion_queues_semantic_cleanup(self):
        pk = self.photo.pk
        with patch("apps.visual_search.semantic_tasks.purge_semantic_photo.delay") as purge, patch("apps.visual_search.purges.dispatch_purge"):
            with self.captureOnCommitCallbacks(execute=True):
                self.photo.delete()
            purge.assert_called_once_with(pk)
        self.assertFalse(SemanticIndexJob.objects.filter(photo_id=pk).exists())

    def test_worker_registers_semantic_tasks(self):
        from config.celery import app
        app.loader.import_default_modules()
        self.assertIn("apps.visual_search.semantic_tasks.index_semantic_photo", app.tasks)


@unittest.skipUnless(os.getenv("SEMANTIC_REAL_PHOTO_MANIFEST") and os.getenv("VISUAL_SEARCH_INTEGRATION_DATABASE_URL"), "Requires authorized real photographs, local CLIP model and disposable pgvector DB")
class SemanticRealPhotoTests(SemanticJourneyTests):
    """Uses actual CLIP inference and pgvector; never substitutes fake embeddings.

    Calls the Celery task body synchronously. Broker/worker delivery is a separate
    staging acceptance step documented in SEMANTIC_REAL_PHOTO_VERIFICATION.md.
    """
    def test_real_model_lifecycle(self):
        from django.core.management import call_command
        from .semantic import purge_gallery, purge_photo
        from .semantic_api import _semantic_results
        from .vector_store import vector_connection
        manifest_path = Path(os.environ["SEMANTIC_REAL_PHOTO_MANIFEST"]).resolve()
        manifest = json.loads(manifest_path.read_text())
        self.assertTrue(manifest.get("authorization"), "Record photo ownership/license authorization")
        self.assertGreaterEqual(len(manifest["photos"]), 4)
        url = os.environ["VISUAL_SEARCH_INTEGRATION_DATABASE_URL"]
        model = os.environ.get("VISUAL_SEARCH_SEMANTIC_MODEL_PATH", "")
        self.assertTrue(Path(model).is_dir() and model, "Provision reviewed CLIP model locally")
        with override_settings(VISUAL_SEARCH_DATABASE_URL=url, VISUAL_SEARCH_SEMANTIC_MODEL_PATH=model):
            with vector_connection() as conn:
                name = conn.execute("SELECT current_database()").fetchone()[0]
                self.assertTrue(name.startswith("lumispixel_visual_search_test"), "Refusing shared vector database")
            call_command("setup_semantic_vector_store")
            photos = {}
            with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
                try:
                    for item in manifest["photos"]:
                        path = (manifest_path.parent / item["file"]).resolve()
                        photo = GalleryPhoto(gallery=self.gallery, photographer=self.profile, status=GalleryPhoto.Status.COMPLETED)
                        photo.file.save(path.name, ContentFile(path.read_bytes()), save=True)
                        photos[item["file"]] = photo
                        job = SemanticIndexJob.objects.get(photo=photo)
                        self.assertEqual(index_semantic_photo.run(job.pk), "indexed")
                        job.refresh_from_db()
                        self.assertEqual(job.status, "completed")
                    for item in manifest["photos"]:
                        ids = _semantic_results(self.gallery, item["query"])
                        self.assertIn(photos[item["file"]].pk, ids[:item.get("top_k", 3)])
                    self.policy.processing_authorized = False
                    self.policy.save()
                    self.assertEqual(purge_semantic_gallery.run(self.gallery.pk), "purged")
                    with vector_connection() as conn:
                        self.assertEqual(conn.execute("SELECT count(*) FROM visual_search.app_semantic_embeddings WHERE gallery_id=%s", (self.gallery.pk,)).fetchone()[0], 0)
                    self.policy.processing_authorized = True
                    self.policy.save()
                    for photo in photos.values():
                        job = schedule_semantic_photo(photo.pk)
                        self.assertEqual(index_semantic_photo.run(job.pk), "indexed")
                    deleted = next(iter(photos.values()))
                    pk = deleted.pk
                    deleted.delete()
                    purge_photo(pk)
                    with vector_connection() as conn:
                        self.assertEqual(conn.execute("SELECT count(*) FROM visual_search.app_semantic_embeddings WHERE photo_id=%s", (pk,)).fetchone()[0], 0)
                finally:
                    purge_gallery(self.gallery.pk)
