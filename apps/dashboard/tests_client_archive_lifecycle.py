from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import (
    Client,
    ClientActivity,
    ClientInvoice,
    ClientNote,
    ClientSession,
    InvoicePayment,
)
from apps.galleries.models import Gallery


def make_owner(email, slug):
    user = User.objects.create_user(
        email=email,
        password="pass12345",
        primary_role=User.PrimaryRole.PHOTOGRAPHER,
        last_active_workspace=User.Workspace.PHOTOGRAPHER,
        email_verified=True,
        account_status=User.AccountStatus.ACTIVE,
    )
    return user, PhotographerProfile.objects.create(
        user=user, slug=slug, onboarding_completed=True
    )


class ClientArchiveLifecycleTests(TestCase):
    def setUp(self):
        self.owner, self.studio = make_owner("lifecycle@example.com", "lifecycle")
        self.other_owner, self.other_studio = make_owner(
            "other-lifecycle@example.com", "other-lifecycle"
        )
        self.record = Client.objects.create(
            photographer=self.studio,
            first_name="Lifecycle",
            last_name="Client",
            email="lifecycle-client@example.com",
        )
        self.url = reverse(
            "photographer_workspace:client_archive_restore", args=[self.record.pk]
        )
        self.client.force_login(self.owner)

    def test_archive_and_restore_are_explicit_idempotent_and_audited(self):
        first = self.client.post(self.url, {"action": "archive"})
        repeated = self.client.post(self.url, {"action": "archive"})

        self.assertEqual(first.status_code, 302)
        self.assertEqual(repeated.status_code, 302)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, Client.Status.ARCHIVED)
        archived_events = ClientActivity.objects.filter(
            client=self.record, event_type=ClientActivity.EventType.CLIENT_ARCHIVED
        )
        self.assertEqual(archived_events.count(), 1)
        self.assertEqual(archived_events.get().actor, self.owner)
        self.assertEqual(archived_events.get().photographer, self.studio)

        self.client.post(self.url, {"action": "restore"})
        self.client.post(self.url, {"action": "restore"})
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, Client.Status.ACTIVE)
        self.assertEqual(
            ClientActivity.objects.filter(
                client=self.record,
                event_type=ClientActivity.EventType.CLIENT_RESTORED,
            ).count(),
            1,
        )

    def test_archive_preserves_related_business_history_and_filter_search(self):
        session = ClientSession.objects.create(
            photographer=self.studio,
            client=self.record,
            session_type="Portrait",
            starts_at=timezone.now(),
        )
        gallery = Gallery.objects.create(
            photographer=self.studio,
            client=self.record,
            name="Lifecycle Gallery",
            slug="lifecycle-gallery",
        )
        invoice = ClientInvoice.objects.create(
            photographer=self.studio, client=self.record, total="250.00"
        )
        payment = InvoicePayment.objects.create(
            photographer=self.studio, invoice=invoice, amount="50.00"
        )
        note = ClientNote.objects.create(
            photographer=self.studio, client=self.record, content="Persist this note."
        )

        self.client.post(self.url, {"action": "archive"})

        for model, pk in (
            (ClientSession, session.pk),
            (Gallery, gallery.pk),
            (ClientInvoice, invoice.pk),
            (InvoicePayment, payment.pk),
            (ClientNote, note.pk),
        ):
            self.assertTrue(model.objects.filter(pk=pk).exists())
        archived = self.client.get(
            reverse("photographer_workspace:clients"),
            {"status": Client.Status.ARCHIVED, "q": "Lifecycle Client"},
        )
        active = self.client.get(
            reverse("photographer_workspace:clients"),
            {"status": Client.Status.ACTIVE, "q": "Lifecycle Client"},
        )
        self.assertContains(archived, "Lifecycle Client")
        self.assertEqual(active.context["result_count"], 0)
        self.assertNotContains(
            active,
            reverse("photographer_workspace:client_detail", args=[self.record.pk]),
        )

    def test_mutation_rejects_cross_workspace_anonymous_and_invalid_actions(self):
        private = Client.objects.create(
            photographer=self.other_studio, first_name="Private", last_name="Client"
        )
        private_url = reverse(
            "photographer_workspace:client_archive_restore", args=[private.pk]
        )
        self.assertEqual(
            self.client.post(private_url, {"action": "archive"}).status_code, 404
        )
        private.refresh_from_db()
        self.assertEqual(private.status, Client.Status.ACTIVE)

        self.assertEqual(self.client.post(self.url, {"action": "delete"}).status_code, 400)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, Client.Status.ACTIVE)
        self.assertFalse(ClientActivity.objects.filter(client=self.record).exists())

        self.client.logout()
        anonymous = self.client.post(self.url, {"action": "archive"})
        self.assertEqual(anonymous.status_code, 302)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, Client.Status.ACTIVE)
