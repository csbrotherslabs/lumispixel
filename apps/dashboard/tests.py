from django.core.management import call_command
from django.test import Client as TestClient, TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from io import BytesIO
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import ClientProfile, PhotographerProfile, User
from apps.clients.models import Client, ClientActivity, ClientInvoice, ClientNote, ClientSession, ClientTask, Lead
from apps.galleries.models import AccessToken, Gallery, GalleryActivity, GalleryInvitation, GalleryPermission, GalleryPhoto, GallerySettings
from apps.ai_engine.models import AIJob, AIProcessingStatus
from apps.dashboard.views import WORKSPACE_MODULES


def make_user(email, role=User.PrimaryRole.PHOTOGRAPHER):
    return User.objects.create_user(email=email, password="pass12345", primary_role=role, last_active_workspace=User.Workspace.PHOTOGRAPHER if role == User.PrimaryRole.PHOTOGRAPHER else User.Workspace.CLIENT, email_verified=True, account_status=User.AccountStatus.ACTIVE)


class PhotographerWorkspaceTests(TestCase):
    def make_photographer(self, completed=True, **profile_kwargs):
        user = make_user(profile_kwargs.pop("email", "photo@example.com"))
        profile = PhotographerProfile.objects.create(user=user, slug=profile_kwargs.pop("slug", "photo"), onboarding_completed=completed, **profile_kwargs)
        return user, profile

    def test_anonymous_client_and_incomplete_access_rules(self):
        url = reverse("photographer_workspace:dashboard")
        self.assertRedirects(self.client.get(url), f"{reverse('accounts:login')}?next={url}", fetch_redirect_response=False)
        client_user = make_user("client@example.com", User.PrimaryRole.CLIENT)
        ClientProfile.objects.create(user=client_user, onboarding_completed=True)
        self.client.force_login(client_user)
        self.assertRedirects(self.client.get(url), reverse("clients:dashboard"), fetch_redirect_response=False)
        self.client.logout()
        incomplete, _ = self.make_photographer(False, email="incomplete@example.com", slug="incomplete")
        self.client.force_login(incomplete)
        self.assertRedirects(self.client.get(url), reverse("photographers:setup-dashboard"), fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse("photographer_workspace:galleries")), reverse("photographers:setup-dashboard"), fetch_redirect_response=False)

    def test_gallery_settings_persist_validate_and_are_owner_scoped(self):
        user, profile = self.make_photographer(True, email="settings@example.com", slug="settings")
        _, other = self.make_photographer(True, email="settings-other@example.com", slug="settings-other")
        gallery = Gallery.objects.create(photographer=profile, name="Coastal Wedding", slug="coastal-wedding")
        private_gallery = Gallery.objects.create(photographer=other, name="Private", slug="private")
        self.client.force_login(user)
        url = reverse("photographer_workspace:gallery_workspace", args=[gallery.pk])
        page = self.client.get(url, {"tab": "settings"})
        self.assertContains(page, "Gallery Settings")
        self.assertContains(page, "Permanently Delete Gallery")
        payload = {
            "action": "save_settings", "general-name": "Coastal Celebration", "general-description": "Client delivery",
            "general-event_date": "2026-08-10", "general-client": "", "general-status": Gallery.Status.PUBLISHED,
            "general-visibility": Gallery.Visibility.PRIVATE, "general-expiration_date": "2026-09-01",
            "settings-accent_color": "#123ABC", "settings-watermark_position": GallerySettings.WatermarkPosition.CENTER,
            "settings-theme": GallerySettings.Theme.EDITORIAL, "settings-allow_downloads": "on", "settings-zip_downloads": "on",
            "settings-download_limit": "12", "settings-enable_favorites": "on", "settings-enable_slideshow": "on",
            "settings-gallery_url": "coastal-client", "settings-meta_title": "Coastal client gallery",
            "settings-meta_description": "A private photography gallery for our coastal celebration.",
        }
        response = self.client.post(url, payload)
        self.assertRedirects(response, f"{url}?tab=settings")
        gallery.refresh_from_db()
        self.assertEqual(gallery.name, "Coastal Celebration")
        self.assertEqual(gallery.settings.download_limit, 12)
        self.assertEqual(gallery.settings.gallery_url, "coastal-client")
        self.assertEqual(self.client.get(reverse("photographer_workspace:gallery_workspace", args=[private_gallery.pk]), {"tab": "settings"}).status_code, 404)

    def test_completed_photographer_dashboard_and_post_login_destination(self):
        user, _ = self.make_photographer(True, business_name="Lumis Studio", display_name="Alex Lens", website_theme=PhotographerProfile.WebsiteTheme.MODERN_STUDIO)
        user.first_name = "Alex"
        user.save(update_fields=["first_name"])
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse("accounts:post-login-redirect")), reverse("photographer_workspace:dashboard"), fetch_redirect_response=False)
        response = self.client.get(reverse("photographer_workspace:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="dashboard-heading"')
        self.assertNotContains(response, '<h2>Dashboard</h2>', html=True)
        self.assertContains(response, "Good ")
        self.assertContains(response, "Alex.")
        self.assertContains(response, "Here’s what’s happening with your business today.")
        self.assertContains(response, "Revenue This Month")
        self.assertContains(response, "Active Clients")
        self.assertContains(response, "Upcoming Bookings")
        self.assertContains(response, "Today’s Schedule")
        self.assertContains(response, "Recent Activity")
        self.assertContains(response, "Business Snapshot")
        self.assertContains(response, "Explore Business Tools")
        self.assertNotContains(response, "Your Website Preview")
        self.assertNotContains(response, "Help and Resources")
        self.assertContains(response, "0")
        self.assertContains(response, f'href="{reverse("core:index")}" aria-label="LumisPixel home"')

    def test_missing_images_and_invalid_theme_fallback_do_not_error(self):
        user, profile = self.make_photographer(True, email="fallback@example.com", slug="fallback", display_name="Fallback Photo")
        PhotographerProfile.objects.filter(pk=profile.pk).update(website_theme="legacy")
        self.client.force_login(user)
        response = self.client.get(reverse("photographer_workspace:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fallback Photo")
        self.assertContains(response, "Dashboard")

    def test_navigation_urls_and_placeholders_resolve(self):
        user, _ = self.make_photographer(True, email="nav@example.com", slug="nav")
        self.client.force_login(user)
        for module in WORKSPACE_MODULES:
            url = reverse(f"photographer_workspace:{module['url_name']}")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, module["title"])
            if module["key"] not in {"dashboard", "crm", "leads", "clients", "galleries", "all_galleries", "gallery_upload_queue", "ai_processing", "bookings"}:
                self.assertContains(response, "Back to Dashboard")

    def test_bookings_dashboard_structure_navigation_and_states(self):
        user, profile = self.make_photographer(True, email="bookings@example.com", slug="bookings")
        client = Client.objects.create(photographer=profile, first_name="Maya", last_name="Cole", email="maya@example.com")
        ClientSession.objects.create(photographer=profile, client=client, session_type="Portrait", starts_at=timezone.now() + timezone.timedelta(days=2), status=ClientSession.Status.CONFIRMED)
        self.client.force_login(user)
        url = reverse("photographer_workspace:bookings")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Business Hub")
        self.assertContains(response, "Overview")
        self.assertContains(response, "Schedule")
        self.assertContains(response, "Manage upcoming sessions, inquiries, payments, and scheduling activity.")
        self.assertContains(response, "New Booking")
        self.assertContains(response, "New Lead")
        self.assertContains(response, "Upcoming Bookings")
        self.assertContains(response, "Today's Schedule")
        self.assertContains(response, "View Calendar")
        self.assertContains(response, "Open Schedule")
        self.assertContains(response, "Search client or session")
        self.assertContains(response, "Payment")
        self.assertContains(response, "Contract")
        self.assertContains(response, "Contact client")
        self.assertContains(response, "New Inquiries")
        self.assertContains(response, "Pending Contracts")
        self.assertContains(response, "Outstanding Payments")
        self.assertContains(response, "Booking Revenue")
        self.assertContains(response, "Booked this month")
        self.assertContains(response, "Revenue collected")
        self.assertContains(response, "Average booking value")
        self.assertContains(response, "Session-type breakdown")
        self.assertContains(response, "Weddings")
        self.assertContains(response, "Recent Activity")
        self.assertContains(response, "No booking activity yet")
        self.assertContains(response, "Block Time")
        self.assertContains(response, "Share Booking Link")
        self.assertContains(response, "Today's Focus")
        self.assertContains(response, "shoots today")
        self.assertContains(response, "contract awaiting signature")
        self.assertContains(response, "gallery ready for delivery")
        self.assertContains(response, "Six-month booking revenue trend")
        self.assertContains(response, "Conversion Rate")
        self.assertContains(response, "Inquiry Pipeline")
        self.assertContains(response, "Contacted")
        self.assertContains(response, "Consultation")
        self.assertContains(response, "Proposal Sent")
        self.assertContains(response, "Estimated open-pipeline value")
        self.assertContains(response, "Action Center")
        self.assertContains(response, "0 active inquiries")
        self.assertContains(response, "7 open actions")
        self.assertContains(response, "contracts awaiting signature")
        self.assertContains(response, "questionnaires awaiting completion")
        self.assertContains(response, "upcoming session this week")
        self.assertContains(response, "Due Soon")
        self.assertContains(response, "Follow Up")
        self.assertContains(response, 'role="tooltip"')
        self.assertContains(response, "Maya Cole")
        self.assertContains(response, f'href="{url}" class="is-active"')
        self.assertContains(self.client.get(url, {"state": "loading"}), "Loading bookings")
        self.assertContains(self.client.get(url, {"state": "error"}), "Bookings could not be loaded")

    def test_schedule_route_controls_and_navigation(self):
        user, profile = self.make_photographer(True, email="schedule@example.com", slug="schedule")
        client = Client.objects.create(photographer=profile, first_name="Maya", last_name="Cole", email="maya.schedule@example.com")
        ClientSession.objects.create(
            photographer=profile, client=client, session_type="Portrait",
            starts_at=timezone.now() + timezone.timedelta(days=2),
            status=ClientSession.Status.CONFIRMED,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:schedule"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Business Hub")
        self.assertContains(response, "View bookings, manage availability, and organize photography work.")
        self.assertContains(response, "New Booking")
        self.assertContains(response, "Block Time")
        self.assertContains(response, "Add Consultation")
        self.assertContains(response, "Add Editing Time")
        self.assertContains(response, "Add Vacation")
        self.assertContains(response, "Create Mini Session")
        self.assertContains(response, "Booking List")
        self.assertContains(response, "Today")
        self.assertContains(response, "Schedule", count=None)
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, 'data-event-drawer role="dialog"')
        self.assertContains(response, 'data-schedule-event="schedule-event-0"')
        self.assertContains(response, "Open Full Booking")
        self.assertContains(response, "Contract not signed")

        list_response = self.client.get(reverse("photographer_workspace:schedule"), {"view": "list"})
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "Booking List view")

    def test_schedule_filters_persist_across_views_and_filter_bookings(self):
        user, profile = self.make_photographer(True, email="filters@example.com", slug="filters")
        client = Client.objects.create(photographer=profile, first_name="Maya", last_name="Cole", email="maya.filters@example.com")
        starts_at = timezone.now() + timezone.timedelta(days=2)
        ClientSession.objects.create(photographer=profile, client=client, session_type="Portrait", location="Studio A", starts_at=starts_at, status=ClientSession.Status.CONFIRMED)
        ClientSession.objects.create(photographer=profile, client=client, session_type="Wedding", location="Garden", starts_at=starts_at, status=ClientSession.Status.CANCELLED)
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:schedule"), {
            "view": "agenda", "q": "Studio A", "session_type": "Portrait", "status": "confirmed",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Maya Cole")
        self.assertNotContains(response, "Wedding ·")
        self.assertContains(response, "3 active")
        self.assertContains(response, "q=Studio+A", count=None)
        self.assertContains(response, "Save View")
        self.assertContains(response, "Show Availability")

        cancelled = self.client.get(reverse("photographer_workspace:schedule"), {
            "view": "list", "status": "cancelled", "show_cancelled": "1",
        })
        self.assertContains(cancelled, "Wedding")
        self.assertContains(cancelled, "Cancelled")

    def test_bookings_schedule_can_mark_an_owned_session_complete(self):
        user, profile = self.make_photographer(True, email="schedule@example.com", slug="schedule")
        client = Client.objects.create(photographer=profile, first_name="Maya", last_name="Cole", email="maya@example.com")
        session = ClientSession.objects.create(
            photographer=profile, client=client, session_type="Portrait consultation",
            starts_at=timezone.now(), status=ClientSession.Status.CONFIRMED,
        )
        self.client.force_login(user)
        response = self.client.post(reverse("photographer_workspace:bookings"), {
            "action": "mark_complete", "session_id": session.pk,
        })
        self.assertRedirects(response, reverse("photographer_workspace:bookings"))
        session.refresh_from_db()
        self.assertEqual(session.status, ClientSession.Status.COMPLETED)

    def test_ai_processing_center_creates_scoped_jobs_and_supports_actions(self):
        user, profile = self.make_photographer(True, email="ai@example.com", slug="ai")
        _, other = self.make_photographer(True, email="other-ai@example.com", slug="other-ai")
        gallery = Gallery.objects.create(photographer=profile, name="AI Wedding", slug="ai-wedding", image_count=80)
        private_gallery = Gallery.objects.create(photographer=other, name="Private AI Gallery", slug="private-ai")
        self.client.force_login(user)

        page = self.client.get(reverse("photographer_workspace:ai_processing"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Monitor and manage AI tasks for every gallery.")
        self.assertContains(page, "Face Detection")
        self.assertContains(page, "Search Indexing")
        self.assertNotContains(page, "Private AI Gallery")

        response = self.client.post(reverse("photographer_workspace:ai_processing"), {
            "gallery_ids": [gallery.pk, private_gallery.pk],
            "task_types": [AIJob.TaskType.FACE_DETECTION, AIJob.TaskType.BLUR_DETECTION],
        })
        self.assertRedirects(response, reverse("photographer_workspace:ai_processing"))
        self.assertEqual(AIJob.objects.for_photographer(profile).count(), 2)
        job = AIJob.objects.get(photographer=profile, task_type=AIJob.TaskType.FACE_DETECTION)
        self.assertEqual(job.progress.total_images, 80)
        self.assertEqual(job.status, AIJob.Status.QUEUED)

        job.status = AIJob.Status.FAILED
        job.error_summary = "Worker unavailable"
        job.save()
        retry = self.client.post(reverse("photographer_workspace:ai_job_action", args=[job.pk]), {"action": "retry"})
        self.assertRedirects(retry, reverse("photographer_workspace:ai_processing"))
        job.refresh_from_db()
        self.assertEqual(job.status, AIJob.Status.QUEUED)
        cancel = self.client.post(reverse("photographer_workspace:ai_job_action", args=[job.pk]), {"action": "cancel"})
        self.assertRedirects(cancel, reverse("photographer_workspace:ai_processing"))
        job.refresh_from_db()
        self.assertEqual(job.status, AIJob.Status.CANCELLED)

    def test_gallery_pages_render_with_active_navigation_and_scoped_records(self):
        user, profile = self.make_photographer(True, email="gallery@example.com", slug="gallery-photo")
        _, other = self.make_photographer(True, email="other-gallery@example.com", slug="other-gallery-photo")
        gallery = Gallery.objects.create(photographer=profile, name="Summer Portraits", slug="summer-portraits", status=Gallery.Status.UPLOADING, image_count=24)
        private_gallery = Gallery.objects.create(photographer=other, name="Private Collection", slug="private-collection")
        self.client.force_login(user)

        expected_pages = [
            ("galleries", "Galleries"),
            ("all_galleries", "All Galleries"),
            ("gallery_upload_queue", "Upload Queue"),
        ]
        for url_name, heading in expected_pages:
            response = self.client.get(reverse(f"photographer_workspace:{url_name}"))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, heading)
            self.assertContains(response, f'href="{reverse(f"photographer_workspace:{url_name}")}" class="is-active"')
            self.assertContains(response, "Summer Portraits")
            self.assertNotContains(response, "Private Collection")

        dashboard = self.client.get(reverse("photographer_workspace:galleries"))
        self.assertContains(dashboard, "Manage gallery delivery, client activity, uploads, and storage.")
        self.assertContains(dashboard, "Active Galleries")
        self.assertContains(dashboard, "Ready to Deliver")
        self.assertContains(dashboard, "Delivery Pipeline")
        self.assertContains(dashboard, "Recent Client Activity")
        self.assertContains(dashboard, "Storage Overview")
        self.assertContains(dashboard, "Upcoming Deadlines")

        detail = self.client.get(reverse("photographer_workspace:gallery_workspace", args=[gallery.pk]))
        self.assertContains(detail, "Gallery summary")
        self.assertContains(detail, "Upload progress")
        self.assertContains(self.client.get(reverse("photographer_workspace:gallery_workspace", args=[gallery.pk]), {"tab": "photos"}), "Search photos")
        self.assertEqual(self.client.get(reverse("photographer_workspace:gallery_workspace", args=[private_gallery.pk])).status_code, 404)

    def test_client_access_settings_and_secure_invitations(self):
        user, profile = self.make_photographer(True, email="access@example.com", slug="access")
        gallery = Gallery.objects.create(photographer=profile, name="Client Delivery", slug="client-delivery")
        self.client.force_login(user)
        url = reverse("photographer_workspace:gallery_workspace", args=[gallery.pk])

        page = self.client.get(url, {"tab": "client-access"})
        self.assertContains(page, "Control who can access this gallery.")
        self.assertContains(page, "Gallery Visibility")
        self.assertContains(page, "Purchase Prints")
        self.assertContains(page, "Client Invitations")

        saved = self.client.post(url, {
            "action": "save_access", "visibility": Gallery.Visibility.PUBLIC,
            "view_gallery": "on", "favorite_photos": "on", "automatic_gallery_lock": "on",
            "watermark": GalleryPermission.Watermark.ALL, "expiration_date": "2027-01-10",
        })
        self.assertRedirects(saved, f"{url}?tab=client-access")
        gallery.refresh_from_db()
        permissions = gallery.permissions
        self.assertEqual(gallery.visibility, Gallery.Visibility.PUBLIC)
        self.assertTrue(permissions.automatic_gallery_lock)
        self.assertFalse(permissions.download_images)
        self.assertEqual(permissions.watermark, GalleryPermission.Watermark.ALL)

        invited = self.client.post(url, {"action": "invite", "client_name": "Avery Stone", "email": "AVERY@example.com"})
        self.assertRedirects(invited, f"{url}?tab=client-access")
        invitation = GalleryInvitation.objects.get(gallery=gallery, email="avery@example.com")
        token = AccessToken.objects.get(invitation=invitation)
        self.assertEqual(len(token.token_hash), 64)
        self.assertNotIn("avery", token.token_hash)

        self.client.post(url, {"action": "disable", "invitation_id": invitation.pk})
        invitation.refresh_from_db()
        token.refresh_from_db()
        self.assertEqual(invitation.status, GalleryInvitation.Status.DISABLED)
        self.assertIsNotNone(token.revoked_at)

    def test_gallery_upload_validates_images_and_scopes_media(self):
        user, profile = self.make_photographer(True, email="upload@example.com", slug="upload")
        other_user, other = self.make_photographer(True, email="upload-other@example.com", slug="upload-other")
        gallery = Gallery.objects.create(photographer=profile, name="Secure", slug="secure")
        image = BytesIO()
        Image.new("RGB", (8, 8), "red").save(image, "JPEG")
        self.client.force_login(user)
        response = self.client.post(reverse("photographer_workspace:gallery_upload_queue"), {
            "gallery": gallery.pk, "files": SimpleUploadedFile("photo.jpg", image.getvalue(), content_type="image/jpeg")
        })
        self.assertEqual(response.status_code, 201)
        photo = GalleryPhoto.objects.get(gallery=gallery)
        self.assertEqual(self.client.get(reverse("photographer_workspace:gallery_photo_media", args=[photo.pk])).status_code, 200)
        invalid = self.client.post(reverse("photographer_workspace:gallery_upload_queue"), {
            "gallery": gallery.pk, "files": SimpleUploadedFile("fake.jpg", b"not an image", content_type="image/jpeg")
        })
        self.assertEqual(invalid.status_code, 400)
        self.client.force_login(other_user)
        self.assertEqual(self.client.get(reverse("photographer_workspace:gallery_photo_media", args=[photo.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("photographer_workspace:gallery_upload_queue"), {"gallery": gallery.pk}).status_code, 404)

    def test_gallery_create_edit_filters_and_bulk_actions(self):
        user, profile = self.make_photographer(True, email="gallery-crud@example.com", slug="gallery-crud")
        client = Client.objects.create(photographer=profile, first_name="Maya", last_name="Cole")
        self.client.force_login(user)

        create = self.client.post(reverse("photographer_workspace:create_gallery"), {
            "name": "Maya & Rowan", "client": client.pk, "event_date": "2026-08-12",
            "description": "A summer celebration", "status": Gallery.Status.DRAFT,
            "visibility": Gallery.Visibility.PASSWORD, "expiration_date": "2026-10-01",
        })
        gallery = Gallery.objects.get(name="Maya & Rowan")
        self.assertRedirects(create, reverse("photographer_workspace:gallery_workspace", args=[gallery.pk]))
        self.assertEqual(gallery.slug, "maya-rowan")
        self.assertIsNotNone(gallery.expires_at)

        filtered = self.client.get(reverse("photographer_workspace:all_galleries"), {"q": "Maya", "client": client.pk, "status": "draft"})
        self.assertContains(filtered, "Maya &amp; Rowan")
        self.assertContains(filtered, 'data-gallery-view="grid"')
        self.assertContains(filtered, 'data-gallery-view="list"')

        self.client.post(reverse("photographer_workspace:gallery_actions"), {"gallery_ids": [gallery.pk], "action": "publish"})
        gallery.refresh_from_db()
        self.assertEqual(gallery.status, Gallery.Status.PUBLISHED)
        self.assertIsNotNone(gallery.published_at)

        self.client.post(reverse("photographer_workspace:gallery_actions"), {"gallery_ids": [gallery.pk], "action": "archive"})
        gallery.refresh_from_db()
        self.assertEqual(gallery.status, Gallery.Status.ARCHIVED)
        self.assertIsNotNone(gallery.archived_at)
        self.assertNotContains(self.client.get(reverse("photographer_workspace:all_galleries")), "Maya &amp; Rowan")
        self.assertContains(self.client.get(reverse("photographer_workspace:gallery_archive")), "Maya &amp; Rowan")

        restored = self.client.post(reverse("photographer_workspace:gallery_archive_actions"), {
            "gallery_ids": [gallery.pk], "action": "restore",
        })
        self.assertRedirects(restored, reverse("photographer_workspace:gallery_archive"))
        gallery.refresh_from_db()
        self.assertEqual(gallery.status, Gallery.Status.DRAFT)
        self.assertEqual(gallery.visibility, Gallery.Visibility.PRIVATE)
        self.assertIsNone(gallery.archived_at)

    def test_archive_actions_enforce_photographer_ownership(self):
        user, profile = self.make_photographer(True, email="archive@example.com", slug="archive")
        _, other = self.make_photographer(True, email="archive-other@example.com", slug="archive-other")
        gallery = Gallery.objects.create(photographer=profile, name="Owned Archive", slug="owned-archive")
        private = Gallery.objects.create(photographer=other, name="Private Archive", slug="private-archive")
        self.client.force_login(user)
        self.client.post(reverse("photographer_workspace:gallery_archive_actions"), {
            "gallery_ids": [gallery.pk, private.pk], "action": "archive", "archive_reason": Gallery.ArchiveReason.COMPLETED,
            "retention_days": "365", "disable_public_access": "on", "confirm_archive": "on",
        })
        gallery.refresh_from_db(); private.refresh_from_db()
        self.assertEqual(gallery.status, Gallery.Status.ARCHIVED)
        self.assertEqual(gallery.archive_reason, Gallery.ArchiveReason.COMPLETED)
        self.assertEqual(private.status, Gallery.Status.DRAFT)
        self.assertNotContains(self.client.get(reverse("photographer_workspace:gallery_archive")), "Private Archive")

    def test_activity_timeline_filters_exports_and_enforces_ownership(self):
        user, profile = self.make_photographer(True, email="activity@example.com", slug="activity")
        _, other = self.make_photographer(True, email="private-activity@example.com", slug="private-activity")
        gallery = Gallery.objects.create(photographer=profile, name="Activity Gallery", slug="activity-gallery")
        private_gallery = Gallery.objects.create(photographer=other, name="Private Activity", slug="private-activity")
        GalleryActivity.objects.create(photographer=profile, gallery=gallery, actor=user,
            actor_type=GalleryActivity.ActorType.PHOTOGRAPHER, event_type=GalleryActivity.EventType.GALLERY_UPDATED,
            title="Gallery updated", description="A visible timeline event.")
        self.client.force_login(user)
        url = reverse("photographer_workspace:gallery_workspace", args=[gallery.pk])

        page = self.client.get(url, {"tab": "activity"})
        self.assertContains(page, "Review everything that has happened in this gallery.")
        self.assertContains(page, "Client Interactions")
        self.assertContains(page, "A visible timeline event.")
        self.assertContains(page, "View details")
        no_results = self.client.get(url, {"tab": "activity", "activity_q": "missing"})
        self.assertContains(no_results, "No activity matches your filters")
        exported = self.client.get(url, {"tab": "activity", "export": "csv"})
        self.assertEqual(exported["Content-Type"], "text/csv")
        self.assertIn(b"Gallery updated", exported.content)
        self.assertEqual(self.client.get(reverse("photographer_workspace:gallery_workspace", args=[private_gallery.pk]), {"tab": "activity"}).status_code, 404)

    def test_album_crud_workspace_and_owner_isolation(self):
        from apps.galleries.models import Album, AlbumPhoto

        user, profile = self.make_photographer(True, email="album-crud@example.com", slug="album-crud")
        _, other = self.make_photographer(True, email="album-other@example.com", slug="album-other")
        gallery = Gallery.objects.create(photographer=profile, name="Wedding", slug="wedding")
        private_gallery = Gallery.objects.create(photographer=other, name="Private", slug="private")
        private_album = Album.objects.create(gallery=private_gallery, name="Private album")
        self.client.force_login(user)

        created = self.client.post(reverse("photographer_workspace:create_album", args=[gallery.pk]), {
            "name": "Golden Hour", "description": "Warm portraits", "visibility": Album.Visibility.PUBLIC, "display_order": 2,
        })
        album = Album.objects.get(gallery=gallery)
        self.assertRedirects(created, reverse("photographer_workspace:album_workspace", args=[album.pk]))
        albums_page = self.client.get(reverse("photographer_workspace:gallery_workspace", args=[gallery.pk]), {"tab": "albums"})
        self.assertContains(albums_page, "Organize galleries into beautiful collections.")
        self.assertContains(albums_page, "Golden Hour")
        self.assertContains(albums_page, "Public Albums")
        self.assertEqual(self.client.get(reverse("photographer_workspace:album_workspace", args=[private_album.pk])).status_code, 404)

        duplicate = self.client.post(reverse("photographer_workspace:album_action", args=[album.pk]), {"action": "duplicate"})
        self.assertEqual(duplicate.status_code, 302)
        self.assertTrue(Album.objects.filter(gallery=gallery, name="Golden Hour Copy").exists())

    def test_clients_workspace_uses_scoped_data_and_directory_controls(self):
        user, profile = self.make_photographer(True, email="directory@example.com", slug="directory")
        _, other = self.make_photographer(True, email="other-directory@example.com", slug="other-directory")
        visible = Client.objects.create(photographer=profile, first_name="Avery", last_name="Stone", email="avery@example.com", tags=["VIP"], client_type=Client.ClientType.INDIVIDUAL)
        ClientInvoice.objects.create(photographer=profile, client=visible, total="900.00", amount_paid="250.00", status=ClientInvoice.Status.SENT)
        Client.objects.create(photographer=other, first_name="Private", last_name="Record")
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:clients"), {"tag": "VIP"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Manage client relationships, projects, payments, and galleries.")
        self.assertContains(response, "Avery Stone")
        self.assertContains(response, "USD 650.00")
        self.assertNotContains(response, "Private Record")
        self.assertContains(response, 'data-client-view="list"')
        self.assertContains(response, 'data-client-view="grid"')

    def test_client_detail_actions_tabs_alerts_and_isolation(self):
        user, profile = self.make_photographer(True, email="detail@example.com", slug="detail")
        _, other = self.make_photographer(True, email="private-detail@example.com", slug="private-detail")
        client = Client.objects.create(photographer=profile, first_name="Avery", last_name="Stone", email="avery@example.com", tags=["VIP"], preferred_contact_method=Client.ContactMethod.EMAIL)
        private = Client.objects.create(photographer=other, first_name="Private", last_name="Client")
        ClientInvoice.objects.create(photographer=profile, client=client, total="500", amount_paid="100", status=ClientInvoice.Status.SENT, due_date="2020-01-01")
        ClientSession.objects.create(photographer=profile, client=client, session_type="Portrait", starts_at=timezone.now() + timezone.timedelta(days=2), status=ClientSession.Status.CONFIRMED)
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:client_detail", args=[client.pk]))
        self.assertContains(response, "Contact details")
        self.assertContains(response, "Outstanding balance")
        self.assertContains(response, "Overdue invoices")
        self.assertContains(response, "Unsigned contracts")
        self.assertContains(response, "Galleries awaiting delivery")
        self.assertContains(response, "USD 400.00")
        self.assertEqual(self.client.get(reverse("photographer_workspace:client_detail", args=[private.pk])).status_code, 404)

        self.client.post(reverse("photographer_workspace:add_client_note", args=[client.pk]), {"content": "Prefers mornings"})
        self.client.post(reverse("photographer_workspace:add_client_task", args=[client.pk]), {"title": "Send guide", "priority": "high"})
        self.assertTrue(ClientNote.objects.filter(client=client, content="Prefers mornings").exists())
        self.assertTrue(ClientTask.objects.filter(client=client, title="Send guide").exists())
        self.client.post(reverse("photographer_workspace:client_archive_restore", args=[client.pk]))
        client.refresh_from_db()
        self.assertEqual(client.status, Client.Status.ARCHIVED)
        self.client.post(reverse("photographer_workspace:client_archive_restore", args=[client.pk]))
        client.refresh_from_db()
        self.assertEqual(client.status, Client.Status.ACTIVE)
        self.assertTrue(ClientActivity.objects.filter(client=client, event_type=ClientActivity.EventType.CLIENT_RESTORED).exists())

    def test_client_mutations_require_csrf(self):
        user, profile = self.make_photographer(True, email="client-csrf@example.com", slug="client-csrf")
        client = Client.objects.create(photographer=profile, first_name="Protected", email="protected@example.com")
        csrf_client = TestClient(enforce_csrf_checks=True)
        csrf_client.force_login(user)
        self.assertEqual(csrf_client.post(reverse("photographer_workspace:client_archive_restore", args=[client.pk])).status_code, 403)
        client.refresh_from_db()
        self.assertEqual(client.status, Client.Status.ACTIVE)

    def test_crm_dashboard_uses_only_logged_in_photographers_records(self):
        user, profile = self.make_photographer(True, email="crm@example.com", slug="crm")
        other_user, other = self.make_photographer(True, email="other-crm@example.com", slug="other-crm")
        Lead.objects.create(photographer=profile, first_name="Visible", status=Lead.Status.NEW)
        Lead.objects.create(photographer=other, first_name="Private", status=Lead.Status.NEW)
        client = Client.objects.create(photographer=profile, first_name="Taylor")
        ClientInvoice.objects.create(photographer=profile, client=client, total="500.00", amount_paid="125.00", status=ClientInvoice.Status.SENT)
        other_client = Client.objects.create(photographer=other, first_name="Other")
        ClientInvoice.objects.create(photographer=other, client=other_client, total="900.00", status=ClientInvoice.Status.SENT)

        self.client.force_login(user)
        response = self.client.get(reverse("photographer_workspace:crm"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Manage leads, clients, tasks, and upcoming activity.")
        self.assertContains(response, "Visible")
        self.assertNotContains(response, "Private")
        self.assertContains(response, "USD 375.00")
        self.assertContains(response, "?status=new")

    def test_active_navigation_item_is_correct(self):
        user, _ = self.make_photographer(True, email="active@example.com", slug="active")
        self.client.force_login(user)
        response = self.client.get(reverse("photographer_workspace:analytics"))
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, "Analytics")

    def test_grouped_navigation_and_profile_menu(self):
        user, _ = self.make_photographer(True, email="grouped@example.com", slug="grouped")
        user.first_name = "Avery"
        user.last_name = "Stone"
        user.save(update_fields=["first_name", "last_name"])
        self.client.force_login(user)
        response = self.client.get(reverse("photographer_workspace:crm"))
        self.assertContains(response, "Business Growth")
        self.assertContains(response, 'aria-controls="nav-group-1"')
        self.assertContains(response, 'aria-label="Clients" data-tooltip="Clients"')
        self.assertContains(response, 'href="/photographer/workspace/leads/"')
        self.assertContains(response, "Avery Stone")
        self.assertContains(response, "Photographer")
        self.assertContains(response, "Business Settings")
        self.assertContains(response, "Sign Out")

    def test_client_cannot_access_module_url(self):
        client_user = make_user("client-module@example.com", User.PrimaryRole.CLIENT)
        ClientProfile.objects.create(user=client_user, onboarding_completed=True)
        self.client.force_login(client_user)
        self.assertRedirects(self.client.get(reverse("photographer_workspace:orders")), reverse("clients:dashboard"), fetch_redirect_response=False)

    def test_system_checks_pass(self):
        call_command("check")

    def test_crm_create_complete_and_convert_workflow(self):
        user, profile = self.make_photographer(True, email="workflow@example.com", slug="workflow")
        self.client.force_login(user)
        response = self.client.post(reverse("photographer_workspace:add_lead"), {
            "first_name": "Jordan", "last_name": "Lee", "email": "jordan@example.com",
        })
        self.assertRedirects(response, reverse("photographer_workspace:crm"))
        lead = Lead.objects.get(photographer=profile, email="jordan@example.com")
        self.assertTrue(ClientActivity.objects.filter(lead=lead, event_type=ClientActivity.EventType.LEAD_CREATED).exists())

        response = self.client.post(reverse("photographer_workspace:create_task"), {
            "title": "Call Jordan", "priority": ClientTask.Priority.HIGH, "lead": lead.pk,
        })
        self.assertRedirects(response, reverse("photographer_workspace:crm"))
        task = ClientTask.objects.get(photographer=profile)
        self.client.post(reverse("photographer_workspace:complete_task", args=[task.pk]))
        task.refresh_from_db()
        self.assertEqual(task.status, ClientTask.Status.COMPLETED)

        self.client.post(reverse("photographer_workspace:convert_lead", args=[lead.pk]))
        lead.refresh_from_db()
        converted = Client.objects.get(converted_lead=lead)
        self.assertEqual(converted.photographer, profile)
        self.assertEqual(lead.status, Lead.Status.BOOKED)
        self.assertTrue(ClientActivity.objects.filter(lead=lead, client=converted, event_type=ClientActivity.EventType.LEAD_CONVERTED).exists())
        self.client.post(reverse("photographer_workspace:convert_lead", args=[lead.pk]))
        self.assertEqual(Client.objects.filter(converted_lead=lead).count(), 1)

    def test_crm_client_creation_and_ownership_protection(self):
        user, profile = self.make_photographer(True, email="create@example.com", slug="create")
        other_user, other = self.make_photographer(True, email="private@example.com", slug="private")
        private_task = ClientTask.objects.create(photographer=other, lead=Lead.objects.create(photographer=other, first_name="Private"), title="Private")
        self.client.force_login(user)
        self.client.post(reverse("photographer_workspace:add_client"), {"first_name": "Sam", "email": "sam@example.com", "status": Client.Status.ACTIVE})
        self.assertTrue(Client.objects.filter(photographer=profile, email="sam@example.com").exists())
        self.assertEqual(self.client.post(reverse("photographer_workspace:complete_task", args=[private_task.pk])).status_code, 404)
        private_task.refresh_from_db()
        self.assertEqual(private_task.status, ClientTask.Status.OPEN)

    def test_add_client_form_renders_crud_system_and_saves_extended_details(self):
        user, profile = self.make_photographer(True, email="form@example.com", slug="form")
        self.client.force_login(user)
        response = self.client.get(reverse("photographer_workspace:add_client"))
        self.assertContains(response, 'class="workspace-form-page"')
        self.assertContains(response, 'class="form-section-card"')
        self.assertContains(response, 'data-upload-dropzone')
        self.assertContains(response, 'data-submit-button')
        self.assertContains(response, '<h1 id="workspace-page-title">Add Client</h1>', count=1, html=True)

        response = self.client.post(reverse("photographer_workspace:add_client"), {
            "first_name": "Avery", "email": "avery@example.com", "status": Client.Status.ACTIVE,
            "address": "10 Main Street", "city": "Portland", "state_province": "Oregon",
            "postal_code": "97205", "country": "United States", "tags_input": "VIP,Portrait",
            "notes": "Prefers morning sessions.",
        })
        self.assertRedirects(response, reverse("photographer_workspace:crm"))
        client = Client.objects.get(photographer=profile, email="avery@example.com")
        self.assertEqual(client.address, "10 Main Street\nPortland\nOregon\n97205\nUnited States")
        self.assertEqual(client.tags, ["VIP", "Portrait"])
        self.assertEqual(client.notes.get().content, "Prefers morning sessions.")

    def test_add_lead_form_uses_crud_design_system(self):
        user, _ = self.make_photographer(True, email="lead-form@example.com", slug="lead-form")
        self.client.force_login(user)
        response = self.client.get(reverse("photographer_workspace:add_lead"))
        self.assertContains(response, 'class="workspace-form-page"')
        self.assertContains(response, "Contact Information")
        self.assertContains(response, "Inquiry Details")
        self.assertContains(response, 'aria-label="Lead setup help"')
        self.assertContains(response, 'data-submit-button')
        self.assertContains(response, "Save Lead")
        self.assertContains(response, '<h1 id="workspace-page-title">Add Lead</h1>', count=1, html=True)

    def test_crm_mutations_require_authentication_and_post(self):
        user, profile = self.make_photographer(True, email="secure@example.com", slug="secure")
        lead = Lead.objects.create(photographer=profile, first_name="Secure")
        url = reverse("photographer_workspace:convert_lead", args=[lead.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(user)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.logout()
        self.client.post(url)
        self.assertFalse(Client.objects.filter(converted_lead=lead).exists())

    def test_leads_workspace_uses_scoped_real_data_and_metrics(self):
        user, profile = self.make_photographer(True, email="pipeline@example.com", slug="pipeline")
        _, other = self.make_photographer(True, email="other-pipeline@example.com", slug="other-pipeline")
        Lead.objects.create(photographer=profile, first_name="Morgan", last_name="Ray", event_type="Wedding", estimated_value="2400", lead_source="Referral")
        Lead.objects.create(photographer=profile, first_name="Casey", status=Lead.Status.BOOKED, estimated_value="1600")
        Lead.objects.create(photographer=other, first_name="Private", estimated_value="9000")
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:leads"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Track inquiries and move prospects toward booking.")
        self.assertContains(response, "Morgan Ray")
        self.assertNotContains(response, "Private")
        self.assertContains(response, "USD 4,000")
        self.assertContains(response, "50.0%")
        self.assertContains(response, 'data-lead-view="board"')
        self.assertContains(response, 'data-stage="proposal_sent"')

    def test_lead_stage_and_bulk_updates_are_scoped(self):
        user, profile = self.make_photographer(True, email="move@example.com", slug="move")
        _, other = self.make_photographer(True, email="other-move@example.com", slug="other-move")
        own = Lead.objects.create(photographer=profile, first_name="Move Me")
        private = Lead.objects.create(photographer=other, first_name="Do Not Move")
        self.client.force_login(user)
        self.client.post(reverse("photographer_workspace:update_lead_status", args=[own.pk]), {"status": Lead.Status.CONTACTED, "next": reverse("photographer_workspace:leads")})
        self.client.post(reverse("photographer_workspace:bulk_update_leads"), {"lead_ids": [own.pk, private.pk], "action": Lead.Status.CONSULTATION})
        own.refresh_from_db()
        private.refresh_from_db()
        self.assertEqual(own.status, Lead.Status.CONSULTATION)
        self.assertEqual(private.status, Lead.Status.NEW)

    def test_lead_actions_validate_log_and_enforce_ownership(self):
        user, profile = self.make_photographer(True, email="actions@example.com", slug="actions")
        _, other = self.make_photographer(True, email="other-actions@example.com", slug="other-actions")
        lead = Lead.objects.create(photographer=profile, first_name="Action", email="action@example.com")
        private = Lead.objects.create(photographer=other, first_name="Private", email="private@example.com")
        self.client.force_login(user)

        self.assertEqual(self.client.post(reverse("photographer_workspace:add_lead_note", args=[private.pk]), {"note": "No access"}).status_code, 404)
        self.client.post(reverse("photographer_workspace:add_lead_note", args=[lead.pk]), {"note": "Prefers afternoons"})
        self.client.post(reverse("photographer_workspace:create_lead_follow_up", args=[lead.pk]), {"title": "Call lead", "due_date": "2026-08-01", "priority": "high"})
        self.client.post(reverse("photographer_workspace:mark_lead_lost", args=[lead.pk]), {"reason": ""})
        lead.refresh_from_db()
        self.assertEqual(lead.status, Lead.Status.NEW)
        self.assertIn("Prefers afternoons", lead.notes)
        self.assertEqual(lead.tasks.get().title, "Call lead")
        self.assertTrue(ClientActivity.objects.filter(lead=lead, event_type=ClientActivity.EventType.NOTE_ADDED).exists())
        self.assertTrue(ClientActivity.objects.filter(lead=lead, event_type=ClientActivity.EventType.FOLLOW_UP_CREATED).exists())

        self.client.post(reverse("photographer_workspace:mark_lead_lost", args=[lead.pk]), {"reason": "Budget changed"})
        lead.refresh_from_db()
        self.assertEqual((lead.status, lead.lost_reason), (Lead.Status.LOST, "Budget changed"))
        self.client.post(reverse("photographer_workspace:archive_lead", args=[lead.pk]))
        lead.refresh_from_db()
        self.assertIsNotNone(lead.archived_at)
        self.assertNotContains(self.client.get(reverse("photographer_workspace:leads")), "action@example.com")

    def test_lead_mutations_require_csrf(self):
        user, profile = self.make_photographer(True, email="csrf@example.com", slug="csrf")
        lead = Lead.objects.create(photographer=profile, first_name="Protected", email="protected@example.com")
        csrf_client = TestClient(enforce_csrf_checks=True)
        csrf_client.force_login(user)
        response = csrf_client.post(reverse("photographer_workspace:mark_lead_booked", args=[lead.pk]))
        self.assertEqual(response.status_code, 403)
        lead.refresh_from_db()
        self.assertEqual(lead.status, Lead.Status.NEW)
