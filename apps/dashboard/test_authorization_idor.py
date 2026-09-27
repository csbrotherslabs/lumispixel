"""Cross-tenant authorization/IDOR regression matrix for private-beta boundaries."""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientInvoice, ClientSession, Contract, Lead
from apps.dashboard.models import StudioMembership
from apps.galleries.models import (
    Album, Gallery, GalleryInvitation, GalleryMultipartUpload, GalleryPhoto,
)


class CrossTenantIdorTests(TestCase):
    def setUp(self):
        self.owner_a = User.objects.create_user(
            email="owner-a@idor.example", password="test-pass",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
        )
        self.owner_b = User.objects.create_user(
            email="owner-b@idor.example", password="test-pass",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
        )
        self.studio_a = PhotographerProfile.objects.create(
            user=self.owner_a, slug="idor-a", onboarding_completed=True,
        )
        self.studio_b = PhotographerProfile.objects.create(
            user=self.owner_b, slug="idor-b", onboarding_completed=True,
        )
        StudioMembership.objects.create(
            studio=self.studio_a, user=self.owner_a, role=StudioMembership.Role.OWNER,
            status=StudioMembership.Status.ACTIVE,
        )
        StudioMembership.objects.create(
            studio=self.studio_b, user=self.owner_b, role=StudioMembership.Role.OWNER,
            status=StudioMembership.Status.ACTIVE,
        )
        self.client_b = Client.objects.create(
            photographer=self.studio_b, first_name="Private", last_name="Client",
            email="private-client@idor.example",
        )
        self.gallery_b = Gallery.objects.create(
            photographer=self.studio_b, client=self.client_b, name="Private Gallery",
            slug="private-gallery",
        )
        self.photo_b = GalleryPhoto.objects.create(
            gallery=self.gallery_b, photographer=self.studio_b,
            file="galleries/b/private.jpg", original_name="private.jpg",
            file_size=100, status=GalleryPhoto.Status.COMPLETED,
        )
        self.album_b = Album.objects.create(gallery=self.gallery_b, name="Private Album")
        self.invitation_b = GalleryInvitation.objects.create(
            gallery=self.gallery_b, client_name="Private Client",
            email="private-client@idor.example",
        )
        self.lead_b = Lead.objects.create(
            photographer=self.studio_b, first_name="Private", last_name="Lead",
            email="private-lead@idor.example",
        )
        self.booking_b = ClientSession.objects.create(
            photographer=self.studio_b, client=self.client_b,
            starts_at=timezone.now() + timedelta(days=1),
        )
        self.invoice_b = ClientInvoice.objects.create(
            photographer=self.studio_b, client=self.client_b, booking=self.booking_b,
            invoice_number="IDOR-B-001", issue_date=timezone.localdate(),
            subtotal=0, discount_total=0, tax_total=0, total=0,
            due_date=timezone.localdate() + timedelta(days=7),
        )
        self.contract_b = Contract.objects.create(
            photographer=self.studio_b, client=self.client_b, booking=self.booking_b,
            title="Private Contract", content="Private contract terms.",
        )
        self.upload_b = GalleryMultipartUpload.objects.create(
            gallery=self.gallery_b, photographer=self.studio_b,
            object_key="private/prod/galleries/b/private.jpg", upload_id="provider-upload-b",
            original_name="private.jpg", content_type="image/jpeg", file_size=100,
        )
        self.client.force_login(self.owner_a)

    def assert_hidden(self, response):
        self.assertIn(response.status_code, (403, 404))

    def test_other_studio_gallery_id_is_hidden(self):
        self.assert_hidden(self.client.get(reverse("photographer_workspace:gallery_workspace", args=[self.gallery_b.pk])))

    def test_other_studio_photo_id_is_hidden(self):
        self.assert_hidden(self.client.get(reverse("photographer_workspace:gallery_photo_media", args=[self.photo_b.pk])))

    def test_other_studio_album_id_is_hidden(self):
        self.assert_hidden(self.client.get(reverse("photographer_workspace:album_workspace", args=[self.album_b.pk])))

    def test_other_studio_client_id_is_hidden(self):
        self.assert_hidden(self.client.get(reverse("photographer_workspace:client_detail", args=[self.client_b.pk])))

    def test_other_studio_lead_id_is_hidden(self):
        self.assert_hidden(self.client.post(
            reverse("photographer_workspace:update_lead_status", args=[self.lead_b.pk]),
            {"status": Lead.Status.CONTACTED},
        ))

    def test_other_studio_booking_id_is_hidden(self):
        self.assert_hidden(self.client.get(reverse("photographer_workspace:booking_detail", args=[self.booking_b.pk])))

    def test_other_studio_contract_id_is_hidden(self):
        self.assert_hidden(self.client.get(reverse("photographer_workspace:contract_detail", args=[self.contract_b.pk])))

    def test_other_studio_invoice_id_is_hidden(self):
        self.assert_hidden(self.client.get(reverse("photographer_workspace:invoice_view", args=[self.invoice_b.pk])))

    def test_other_studio_gallery_invitation_id_is_hidden(self):
        self.assert_hidden(self.client.post(
            reverse("galleries:resend_client_gallery_invitation",
                    args=[self.gallery_b.pk, self.invitation_b.pk])
        ))

    @patch("apps.dashboard.views.list_multipart_parts")
    def test_other_studio_multipart_uuid_is_hidden_before_provider_call(self, provider):
        response = self.client.post(
            reverse("photographer_workspace:gallery_multipart_resume", args=[self.upload_b.pk])
        )
        self.assert_hidden(response)
        provider.assert_not_called()


class WorkerAssignmentIdorTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@worker-idor.example", password="test-pass",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
        )
        self.worker = User.objects.create_user(
            email="worker@worker-idor.example", password="test-pass",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
        )
        self.studio = PhotographerProfile.objects.create(
            user=self.owner, slug="worker-idor", onboarding_completed=True,
        )
        StudioMembership.objects.create(
            studio=self.studio, user=self.owner, role=StudioMembership.Role.OWNER,
            status=StudioMembership.Status.ACTIVE,
        )
        self.membership = StudioMembership.objects.create(
            studio=self.studio, user=self.worker, role=StudioMembership.Role.PHOTOGRAPHER,
            status=StudioMembership.Status.ACTIVE,
        )
        self.assigned = Gallery.objects.create(
            photographer=self.studio, name="Assigned", slug="assigned-idor",
        )
        self.assigned.assigned_members.add(self.membership)
        self.unassigned = Gallery.objects.create(
            photographer=self.studio, name="Unassigned", slug="unassigned-idor",
        )
        self.client.force_login(self.worker)

    def test_worker_can_open_assigned_gallery(self):
        response = self.client.get(reverse("photographer_workspace:gallery_workspace", args=[self.assigned.pk]))
        self.assertEqual(response.status_code, 200)

    def test_worker_cannot_idor_unassigned_gallery(self):
        response = self.client.get(reverse("photographer_workspace:gallery_workspace", args=[self.unassigned.pk]))
        self.assertIn(response.status_code, (403, 404))
