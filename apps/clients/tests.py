from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import PhotographerProfile, User

from .models import Client, ClientActivity, ClientNote, ClientTask, Lead


class CrmModelTests(TestCase):
    def setUp(self):
        self.owner_user = User.objects.create_user(email="owner@example.com", password="test-pass")
        self.other_user = User.objects.create_user(email="other@example.com", password="test-pass")
        self.owner = PhotographerProfile.objects.create(user=self.owner_user, slug="owner")
        self.other = PhotographerProfile.objects.create(user=self.other_user, slug="other")

    def test_workspace_query_helpers_isolate_records(self):
        owned = Lead.objects.create(photographer=self.owner, first_name="Ada", email="ada@example.com")
        Lead.objects.create(photographer=self.other, first_name="Grace", email="grace@example.com")

        self.assertEqual(list(Lead.objects.for_photographer(self.owner)), [owned])
        self.assertEqual(list(Lead.objects.for_user(self.owner_user)), [owned])

    def test_crm_relationships_accept_same_owner(self):
        lead = Lead.objects.create(photographer=self.owner, first_name="Ada")
        client = Client.objects.create(photographer=self.owner, converted_lead=lead, first_name="Ada")
        note = ClientNote(photographer=self.owner, client=client, content="Prefers morning calls")
        task = ClientTask(photographer=self.owner, client=client, title="Send proposal")
        activity = ClientActivity(
            photographer=self.owner,
            client=client,
            lead=lead,
            event_type=ClientActivity.EventType.LEAD_CONVERTED,
        )

        note.full_clean()
        task.full_clean()
        activity.full_clean()

    def test_cross_workspace_relationships_are_rejected(self):
        other_lead = Lead.objects.create(photographer=self.other, first_name="Grace")
        other_client = Client.objects.create(photographer=self.other, first_name="Grace")

        with self.assertRaises(ValidationError):
            Client(photographer=self.owner, converted_lead=other_lead, first_name="Grace").full_clean()
        with self.assertRaises(ValidationError):
            ClientNote(photographer=self.owner, client=other_client, content="Private").full_clean()
        with self.assertRaises(ValidationError):
            ClientTask(photographer=self.owner, lead=other_lead, title="Private").full_clean()

    def test_task_requires_a_related_lead_or_client(self):
        with self.assertRaises(ValidationError):
            ClientTask(photographer=self.owner, title="Unrelated").full_clean()
