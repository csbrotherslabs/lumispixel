"""Safety and UX regression coverage for real-photo semantic verification."""
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings


class RealPhotoVerificationSafetyTests(SimpleTestCase):
    def test_missing_photo_rejected_before_model_or_database(self):
        with self.assertRaisesMessage(CommandError, "Image not found"):
            call_command("verify_semantic_real_photo", image="/nonexistent/consented-photo.jpg", query="first dance")

    @override_settings(
        VISUAL_SEARCH_SEMANTIC_ENABLED=False,
        VISUAL_SEARCH_SEMANTIC_POLICY_APPROVED=False,
    )
    def test_disabled_semantic_feature_fails_closed(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "photo.jpg"
            path.write_bytes(b"placeholder")
            with self.assertRaisesMessage(CommandError, "VISUAL_SEARCH_SEMANTIC_ENABLED"):
                call_command("verify_semantic_real_photo", image=str(path), query="first dance")

    def test_create_form_has_bottom_submit_action(self):
        source = Path("templates/photographer_workspace/galleries/form.html").read_text()
        create_part = source.split("{% if is_create_gallery %}", 1)[1].split("{% else %}", 1)[0]
        self.assertIn('class="lp-gallery-create-bottom-actions"', create_part)
        self.assertIn('<span>Create Gallery</span>', create_part)

    def test_discovery_copy_is_concise(self):
        source = Path("templates/photographer_workspace/galleries/components/ai_photo_discovery.html").read_text()
        self.assertNotIn("until their policies and safeguards are approved", source)
        self.assertIn("Both options start off.", source)
