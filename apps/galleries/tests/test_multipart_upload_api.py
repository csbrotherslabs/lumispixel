import json
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import PhotographerProfile, User
from apps.billing.models import PlanAllowance
from apps.billing.services import select_plan
from apps.galleries.models import Gallery, GalleryMultipartUpload, GalleryPhoto


@override_settings(
    GALLERY_STORAGE_BACKEND="b2",
    GALLERY_STORAGE_ENVIRONMENT="dev",
    B2_BUCKET_NAME="test-bucket",
    B2_ACCESS_KEY_ID="test-key",
    B2_SECRET_ACCESS_KEY="test-secret",
    B2_REGION="us-east-005",
    B2_ENDPOINT_URL="https://s3.us-east-005.backblazeb2.com",
)
class MultipartUploadApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="multipart@example.com", password="testpass",
            primary_role=User.PrimaryRole.PHOTOGRAPHER, email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.profile = PhotographerProfile.objects.create(
            user=self.user, slug="multipart", onboarding_completed=True
        )
        self.gallery = Gallery.objects.create(
            photographer=self.profile, name="Direct Upload", slug="direct-upload"
        )
        self.client.force_login(self.user)


    def _set_storage_allowance(self, bytes_allowed):
        allowance = PlanAllowance.objects.get(
            plan=self.profile.billing_subscription.plan,
            key="storage_bytes",
        )
        allowance.limit_type = PlanAllowance.LimitType.NUMERIC
        allowance.value = bytes_allowed
        allowance.save(update_fields=["limit_type", "value", "updated_at"])

    @patch("apps.dashboard.views.initiate_multipart", return_value="b2-upload-id")
    def test_initiate_enforces_active_plan_storage_allowance(self, initiate):
        self._set_storage_allowance(5 * 1024 * 1024)

        response = self.client.post(
            reverse("photographer_workspace:gallery_multipart_initiate"),
            data=json.dumps({
                "gallery": self.gallery.pk, "name": "too-large.jpg",
                "content_type": "image/jpeg", "size": 6 * 1024 * 1024,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Not enough storage to upload this file.")
        initiate.assert_not_called()

    @patch("apps.dashboard.views.initiate_multipart", return_value="b2-upload-id")
    def test_initiate_uses_new_plan_allowance_after_plan_change(self, initiate):
        self._set_storage_allowance(5 * 1024 * 1024)
        pro = select_plan(self.profile, "pro", enforce_customer_selectable=False)
        pro_allowance = PlanAllowance.objects.get(plan=pro.plan, key="storage_bytes")
        pro_allowance.limit_type = PlanAllowance.LimitType.NUMERIC
        pro_allowance.value = 10 * 1024 * 1024
        pro_allowance.save(update_fields=["limit_type", "value", "updated_at"])

        response = self.client.post(
            reverse("photographer_workspace:gallery_multipart_initiate"),
            data=json.dumps({
                "gallery": self.gallery.pk, "name": "allowed.jpg",
                "content_type": "image/jpeg", "size": 6 * 1024 * 1024,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        initiate.assert_called_once()

    @patch("apps.dashboard.views.initiate_multipart", return_value="b2-upload-id")
    def test_initiate_counts_active_multipart_reservations_against_plan_storage(self, initiate):
        self._set_storage_allowance(10 * 1024 * 1024)
        GalleryMultipartUpload.objects.create(
            gallery=self.gallery,
            photographer=self.profile,
            object_key=f"private/dev/galleries/{self.profile.pk}/{self.gallery.pk}/originals/reserved.jpg",
            upload_id="reserved-upload",
            original_name="reserved.jpg",
            content_type="image/jpeg",
            file_size=6 * 1024 * 1024,
        )

        response = self.client.post(
            reverse("photographer_workspace:gallery_multipart_initiate"),
            data=json.dumps({
                "gallery": self.gallery.pk, "name": "second.jpg",
                "content_type": "image/jpeg", "size": 6 * 1024 * 1024,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        initiate.assert_not_called()

    @patch("apps.dashboard.views.initiate_multipart", return_value="b2-upload-id")
    def test_initiate_is_owner_scoped_and_uses_uuid_key(self, initiate):
        response = self.client.post(
            reverse("photographer_workspace:gallery_multipart_initiate"),
            data=json.dumps({
                "gallery": self.gallery.pk, "name": "same-name.jpg",
                "content_type": "image/jpeg", "size": 6 * 1024 * 1024,
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        session = GalleryMultipartUpload.objects.get(pk=response.json()["upload"])
        self.assertTrue(session.object_key.startswith(
            f"private/dev/galleries/{self.profile.pk}/{self.gallery.pk}/originals/"
        ))
        self.assertTrue(session.object_key.endswith(".jpg"))
        self.assertNotIn("same-name", session.object_key)
        initiate.assert_called_once()


    @patch("apps.dashboard.views.list_multipart_parts", return_value=[
        {"part_number": 1, "etag": '"etag-1"', "size": 5 * 1024 * 1024}
    ])
    def test_resume_returns_existing_b2_parts(self, list_parts):
        session = GalleryMultipartUpload.objects.create(
            gallery=self.gallery, photographer=self.profile,
            object_key=f"private/dev/galleries/{self.profile.pk}/{self.gallery.pk}/originals/id.jpg",
            upload_id="upload-id", original_name="photo.jpg",
            content_type="image/jpeg", file_size=6 * 1024 * 1024,
        )
        response = self.client.post(
            reverse("photographer_workspace:gallery_multipart_resume", args=[session.pk]),
            data="{}", content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["upload"], str(session.pk))
        self.assertEqual(response.json()["parts"][0]["part_number"], 1)
        self.assertEqual(response.json()["parts"][0]["etag"], '"etag-1"')
        list_parts.assert_called_once_with(key=session.object_key, upload_id=session.upload_id)

    @patch("apps.dashboard.views.sign_part", return_value="https://b2.example/presigned")
    def test_part_signing_returns_short_lived_provider_url(self, signer):
        session = GalleryMultipartUpload.objects.create(
            gallery=self.gallery, photographer=self.profile,
            object_key=f"private/dev/galleries/{self.profile.pk}/{self.gallery.pk}/originals/id.jpg",
            upload_id="upload-id", original_name="photo.jpg",
            content_type="image/jpeg", file_size=6 * 1024 * 1024,
        )
        response = self.client.post(
            reverse("photographer_workspace:gallery_multipart_sign_part", args=[session.pk]),
            data=json.dumps({"part_number": 1}), content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["url"], "https://b2.example/presigned")

    @patch("apps.dashboard.views.complete_multipart")
    def test_complete_creates_gallery_photo_only_after_b2_completion(self, complete):
        session = GalleryMultipartUpload.objects.create(
            gallery=self.gallery, photographer=self.profile,
            object_key=f"private/dev/galleries/{self.profile.pk}/{self.gallery.pk}/originals/id.jpg",
            upload_id="upload-id", original_name="photo.jpg",
            content_type="image/jpeg", file_size=6 * 1024 * 1024,
        )
        response = self.client.post(
            reverse("photographer_workspace:gallery_multipart_complete", args=[session.pk]),
            data=json.dumps({"parts": [{"part_number": 1, "etag": '"etag-1"'}]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        photo = GalleryPhoto.objects.get(pk=response.json()["photo"]["id"])
        self.assertEqual(photo.file.name, f"galleries/{self.profile.pk}/{self.gallery.pk}/originals/id.jpg")
        self.gallery.refresh_from_db()
        self.assertEqual(self.gallery.image_count, 1)
        self.assertEqual(self.gallery.storage_used, session.file_size)

    @patch("apps.dashboard.views.abort_multipart")
    def test_abort_marks_session_without_creating_photo(self, abort):
        session = GalleryMultipartUpload.objects.create(
            gallery=self.gallery, photographer=self.profile,
            object_key=f"private/dev/galleries/{self.profile.pk}/{self.gallery.pk}/originals/id.jpg",
            upload_id="upload-id", original_name="photo.jpg",
            content_type="image/jpeg", file_size=6 * 1024 * 1024,
        )
        response = self.client.post(
            reverse("photographer_workspace:gallery_multipart_abort", args=[session.pk])
        )
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertIsNotNone(session.aborted_at)
        self.assertFalse(GalleryPhoto.objects.exists())
