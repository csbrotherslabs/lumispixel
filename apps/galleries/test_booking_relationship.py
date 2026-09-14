from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientSession
from apps.galleries.forms import GalleryForm
from apps.galleries.models import Gallery


class GalleryBookingRelationshipTests(TestCase):
    def make_photographer(self, email, slug):
        user = User.objects.create(
            email=email,
            first_name="Test",
            last_name="Photographer",
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            last_active_workspace=User.Workspace.PHOTOGRAPHER,
        )
        return PhotographerProfile.objects.create(
            user=user,
            slug=slug,
            business_name=f"{slug.title()} Studio",
            onboarding_completed=True,
        )

    def setUp(self):
        self.photographer = self.make_photographer("owner@example.com", "owner")
        self.other_photographer = self.make_photographer("other@example.com", "other")
        self.client = Client.objects.create(photographer=self.photographer, first_name="Maya", last_name="Reed")
        self.second_client = Client.objects.create(photographer=self.photographer, first_name="Rowan", last_name="Lee")
        self.other_client = Client.objects.create(photographer=self.other_photographer, first_name="Private", last_name="Client")
        starts_at = timezone.now()
        self.booking = ClientSession.objects.create(
            photographer=self.photographer,
            client=self.client,
            event_kind=ClientSession.EventKind.BOOKING,
            session_type="Wedding",
            starts_at=starts_at,
            status=ClientSession.Status.COMPLETED,
        )
        self.wrong_client_booking = ClientSession.objects.create(
            photographer=self.photographer,
            client=self.second_client,
            event_kind=ClientSession.EventKind.BOOKING,
            session_type="Portrait",
            starts_at=starts_at,
        )
        self.other_booking = ClientSession.objects.create(
            photographer=self.other_photographer,
            client=self.other_client,
            event_kind=ClientSession.EventKind.BOOKING,
            session_type="Event",
            starts_at=starts_at,
        )
        self.consultation = ClientSession.objects.create(
            photographer=self.photographer,
            client=self.client,
            event_kind=ClientSession.EventKind.CONSULTATION,
            session_type="Consultation",
            starts_at=starts_at,
        )

    def test_gallery_validates_booking_ownership_and_client(self):
        Gallery(
            photographer=self.photographer,
            client=self.client,
            booking=self.booking,
            name="Maya Wedding",
            slug="maya-wedding",
        ).full_clean()

        with self.assertRaises(ValidationError):
            Gallery(
                photographer=self.photographer,
                client=self.client,
                booking=self.other_booking,
                name="Other Owner",
                slug="other-owner",
            ).full_clean()

        with self.assertRaises(ValidationError):
            Gallery(
                photographer=self.photographer,
                client=self.client,
                booking=self.wrong_client_booking,
                name="Other Client",
                slug="other-client",
            ).full_clean()

    def test_booking_delete_sets_gallery_relationship_null(self):
        gallery = Gallery.objects.create(
            photographer=self.photographer,
            client=self.client,
            booking=self.booking,
            name="Durable Gallery",
            slug="durable-gallery",
        )
        self.booking.delete()
        gallery.refresh_from_db()
        self.assertIsNone(gallery.booking_id)

    def test_form_scopes_booking_choices_to_owner_and_real_bookings(self):
        form = GalleryForm(photographer=self.photographer)
        ids = set(form.fields["booking"].queryset.values_list("pk", flat=True))
        self.assertIn(self.booking.pk, ids)
        self.assertIn(self.wrong_client_booking.pk, ids)
        self.assertNotIn(self.other_booking.pk, ids)
        self.assertNotIn(self.consultation.pk, ids)

    def test_form_rejects_booking_for_different_selected_client(self):
        form = GalleryForm(
            data={
                "name": "Maya Wedding",
                "client": self.client.pk,
                "booking": self.wrong_client_booking.pk,
                "status": Gallery.Status.DRAFT,
                "visibility": Gallery.Visibility.PRIVATE,
            },
            photographer=self.photographer,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("booking", form.errors)

    def test_form_persists_matching_booking(self):
        form = GalleryForm(
            data={
                "name": "Maya Wedding",
                "client": self.client.pk,
                "booking": self.booking.pk,
                "status": Gallery.Status.DRAFT,
                "visibility": Gallery.Visibility.PRIVATE,
            },
            photographer=self.photographer,
        )
        self.assertTrue(form.is_valid(), form.errors)
        gallery = form.save(commit=False)
        gallery.slug = "maya-wedding"
        gallery.full_clean()
        gallery.save()
        self.assertEqual(gallery.booking_id, self.booking.pk)
