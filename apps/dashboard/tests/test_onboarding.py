from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientSession
from apps.galleries.models import Gallery, GalleryActivity, GalleryPhoto
from apps.dashboard.access import StudioAccess
from apps.dashboard.models import StudioMembership
from apps.dashboard.onboarding import build_onboarding


class OnboardingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="setup@example.com", password="TestPass123!",
            account_status=User.AccountStatus.ACTIVE, email_verified=True,
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
        )
        self.studio = PhotographerProfile.objects.create(user=self.user, onboarding_completed=True)
        self.access = StudioAccess(self.studio, StudioMembership.Role.OWNER)

    def test_empty_workspace_has_four_steps_and_client_next(self):
        data = build_onboarding(self.access)
        self.assertEqual(data["completed"], 0)
        self.assertEqual(len(data["steps"]), 4)
        self.assertEqual(data["next_step"]["url"], reverse("photographer_workspace:add_client"))

    def test_progress_is_studio_scoped_and_remains_visible_after_client(self):
        other_user = User.objects.create_user(email="other@example.com", password="TestPass123!")
        other = PhotographerProfile.objects.create(user=other_user)
        Client.objects.create(photographer=other, first_name="Other", email="other-client@example.com")
        self.assertEqual(build_onboarding(self.access)["completed"], 0)
        Client.objects.create(photographer=self.studio, first_name="Own", email="own-client@example.com")
        data = build_onboarding(self.access)
        self.assertEqual(data["completed"], 1)
        self.assertEqual(data["next_step"]["title"], "Create a booking")
        self.client.force_login(self.user)
        response = self.client.get(reverse("photographer_workspace:dashboard"))
        self.assertContains(response, "Get your workspace ready")
        self.assertContains(response, "1 of 4 complete")

    def test_member_does_not_receive_owner_setup_data(self):
        self.assertIsNone(build_onboarding(StudioAccess(
            self.studio, StudioMembership.Role.MANAGER, membership=object(),
        )))

    def test_completed_upload_and_recorded_share_finish_checklist(self):
        client = Client.objects.create(photographer=self.studio, first_name="Own")
        ClientSession.objects.create(photographer=self.studio, client=client,
                                     session_type="Portrait", starts_at=timezone.now())
        gallery = Gallery.objects.create(photographer=self.studio, name="Portrait", slug="portrait")
        photo = GalleryPhoto.objects.create(photographer=self.studio, gallery=gallery, original_name="portrait.jpg",
                                            status=GalleryPhoto.Status.FAILED)
        self.assertEqual(build_onboarding(self.access)["completed"], 2)
        photo.status = GalleryPhoto.Status.COMPLETED
        photo.save(update_fields=["status"])
        GalleryActivity.objects.create(photographer=self.studio, gallery=gallery,
                                       event_type=GalleryActivity.EventType.GALLERY_SHARED)
        data = build_onboarding(self.access)
        self.assertEqual(data["completed"], 4)
        self.assertTrue(data["complete"])
        self.assertIsNone(data["next_step"])
        self.client.force_login(self.user)
        response = self.client.get(reverse("photographer_workspace:dashboard"))
        self.assertContains(response, "Setup complete")
        self.assertNotContains(response, "Get your workspace ready")
