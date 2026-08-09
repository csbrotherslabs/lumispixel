from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile
from apps.clients.models import Client, ClientActivity, ClientNote
from apps.clients.services import create_client_note
from apps.dashboard.models import StudioMembership
from apps.dashboard.tests_lead_edit import make_user


class ClientNotesActivityTests(TestCase):
    def setUp(self):
        self.owner = make_user("notes-owner@example.com")
        self.studio = PhotographerProfile.objects.create(
            user=self.owner, slug="notes-studio", onboarding_completed=True
        )
        self.client_record = Client.objects.create(
            photographer=self.studio, first_name="Avery", last_name="Morgan"
        )
        self.add_url = reverse(
            "photographer_workspace:add_client_note", args=[self.client_record.pk]
        )
        self.detail_url = reverse(
            "photographer_workspace:client_detail", args=[self.client_record.pk]
        )

    def test_add_note_persists_server_owned_metadata_and_audit_event(self):
        self.client.force_login(self.owner)

        response = self.client.post(self.add_url, {"content": "  Call after 10am.  "})

        self.assertRedirects(response, self.detail_url)
        note = ClientNote.objects.get()
        self.assertEqual(note.content, "Call after 10am.")
        self.assertEqual(note.client, self.client_record)
        self.assertEqual(note.photographer, self.studio)
        self.assertEqual(note.author, self.owner)
        self.assertIsNotNone(note.created_at)
        self.assertIsNotNone(note.updated_at)
        event = ClientActivity.objects.get(event_type=ClientActivity.EventType.NOTE_ADDED)
        self.assertEqual(event.actor, self.owner)
        self.assertEqual(event.client, self.client_record)
        self.assertEqual(event.photographer, self.studio)
        self.assertEqual(event.metadata, {"note_id": note.pk})
        self.client.logout()
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.detail_url), "Call after 10am.")
        self.assertContains(self.client.get(self.detail_url), self.owner.email)

    def test_note_validation_rejects_blank_and_oversize_content(self):
        self.client.force_login(self.owner)
        self.client.post(self.add_url, {"content": " \n "})
        self.client.post(self.add_url, {"content": "x" * 5001})
        self.assertFalse(ClientNote.objects.exists())
        self.assertFalse(ClientActivity.objects.exists())

        with self.assertRaises(ValidationError):
            ClientNote(
                photographer=self.studio, client=self.client_record, content="   "
            ).full_clean()

    def test_note_and_audit_creation_are_atomic(self):
        with patch.object(ClientActivity.objects, "create", side_effect=RuntimeError("audit failed")):
            with self.assertRaises(RuntimeError):
                create_client_note(
                    client=self.client_record, content="Must roll back", actor=self.owner
                )
        self.assertFalse(ClientNote.objects.exists())

    def test_note_display_escapes_html_and_preserves_line_breaks(self):
        ClientNote.objects.create(
            photographer=self.studio,
            client=self.client_record,
            author=self.owner,
            content='<script>alert("x")</script>\nSecond line',
        )
        self.client.force_login(self.owner)
        response = self.client.get(self.detail_url)
        self.assertNotContains(response, '<script>alert("x")</script>', html=False)
        self.assertContains(response, "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;<br>", html=False)

    def test_anonymous_unassigned_and_cross_workspace_note_access_is_denied(self):
        self.assertEqual(self.client.post(self.add_url, {"content": "Anonymous"}).status_code, 302)
        member_user = make_user("notes-member@example.com")
        membership = StudioMembership.objects.create(
            studio=self.studio,
            user=member_user,
            role=StudioMembership.Role.PHOTOGRAPHER,
            status=StudioMembership.Status.ACTIVE,
        )
        self.client.force_login(member_user)
        self.assertEqual(self.client.post(self.add_url, {"content": "Unassigned"}).status_code, 404)
        self.client_record.assigned_members.add(membership)
        self.assertEqual(self.client.post(self.add_url, {"content": "Assigned"}).status_code, 302)
        self.assertEqual(ClientNote.objects.get().author, member_user)

        other_owner = make_user("notes-other@example.com")
        other_studio = PhotographerProfile.objects.create(
            user=other_owner, slug="notes-other", onboarding_completed=True
        )
        private_client = Client.objects.create(photographer=other_studio, first_name="Private")
        private_url = reverse("photographer_workspace:add_client_note", args=[private_client.pk])
        self.assertEqual(self.client.post(private_url, {"content": "Cross tenant"}).status_code, 404)
        self.assertFalse(ClientNote.objects.filter(client=private_client).exists())

    def test_activity_is_client_and_workspace_scoped_with_stable_newest_first_order(self):
        other_client = Client.objects.create(photographer=self.studio, first_name="Other")
        other_owner = make_user("activity-other@example.com")
        other_studio = PhotographerProfile.objects.create(
            user=other_owner, slug="activity-other", onboarding_completed=True
        )
        private_client = Client.objects.create(photographer=other_studio, first_name="Private")
        older = ClientActivity.objects.create(
            photographer=self.studio,
            client=self.client_record,
            actor=self.owner,
            event_type=ClientActivity.EventType.CLIENT_UPDATED,
            description="Older visible event",
        )
        newer = ClientActivity.objects.create(
            photographer=self.studio,
            client=self.client_record,
            actor=self.owner,
            event_type=ClientActivity.EventType.CLIENT_ARCHIVED,
            description="Newer visible event",
        )
        ClientActivity.objects.filter(pk=older.pk).update(
            occurred_at=timezone.now() - timedelta(minutes=1)
        )
        ClientActivity.objects.create(
            photographer=self.studio, client=other_client,
            event_type=ClientActivity.EventType.CLIENT_UPDATED,
            description="Other client secret",
        )
        ClientActivity.objects.create(
            photographer=other_studio, client=private_client,
            event_type=ClientActivity.EventType.CLIENT_UPDATED,
            description="Other workspace secret",
        )
        self.client.force_login(self.owner)
        response = self.client.get(self.detail_url, {"tab": "activity"})
        body = response.content.decode()
        self.assertLess(body.index("Newer visible event"), body.index("Older visible event"))
        self.assertNotContains(response, "Other client secret")
        self.assertNotContains(response, "Other workspace secret")
        self.assertContains(response, self.owner.email)
        self.assertEqual(response.context["activities"][0].pk, newer.pk)

