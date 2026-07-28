from django.core.exceptions import ValidationError
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User

from .models import Client, ClientActivity, ClientInvoice, ClientNote, ClientSession, ClientTask, Lead


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

    def test_lead_pipeline_helpers_are_scoped_and_include_empty_stages(self):
        today = timezone.localdate()
        overdue = Lead.objects.create(
            photographer=self.owner,
            first_name="Overdue",
            estimated_value=Decimal("1200.00"),
            next_follow_up=today - timedelta(days=1),
        )
        Lead.objects.create(
            photographer=self.owner,
            first_name="Booked",
            status=Lead.Status.BOOKED,
            estimated_value=Decimal("800.00"),
            next_follow_up=today - timedelta(days=1),
        )
        Lead.objects.create(
            photographer=self.owner,
            first_name="Lost",
            status=Lead.Status.LOST,
            estimated_value=Decimal("900.00"),
        )
        Lead.objects.create(
            photographer=self.other,
            first_name="Private",
            estimated_value=Decimal("5000.00"),
            next_follow_up=today - timedelta(days=1),
        )

        leads = Lead.objects.for_photographer(self.owner)
        self.assertEqual(list(leads.overdue_followups()), [overdue])
        self.assertEqual(leads.pipeline_value(), Decimal("2000.00"))
        self.assertEqual(leads.stage_counts()[Lead.Status.NEW], 1)
        self.assertEqual(leads.stage_counts()[Lead.Status.CONTACTED], 0)
        self.assertAlmostEqual(leads.conversion_rate(), 100 / 3)

    def test_safe_conversion_is_idempotent_and_preserves_owner_and_tags(self):
        lead = Lead.objects.create(
            photographer=self.owner,
            first_name="Ada",
            last_name="Lovelace",
            tags=["wedding", "priority"],
        )

        client, created = lead.convert_to_client()
        duplicate, duplicate_created = lead.convert_to_client()

        self.assertTrue(created)
        self.assertFalse(duplicate_created)
        self.assertEqual(client, duplicate)
        self.assertEqual(client.photographer, self.owner)
        self.assertEqual(client.tags, lead.tags)
        self.assertEqual(Lead.objects.get(pk=lead.pk).status, Lead.Status.BOOKED)

    def test_lead_validation_rejects_invalid_value_tags_and_lost_reason(self):
        lead = Lead(
            photographer=self.owner,
            first_name="Invalid",
            estimated_value=Decimal("-1.00"),
            tags="not-a-list",
            lost_reason="No response",
        )

        with self.assertRaises(ValidationError) as raised:
            lead.full_clean()

        self.assertEqual(set(raised.exception.message_dict), {"estimated_value", "tags", "lost_reason"})

    def test_client_fields_and_contact_validation(self):
        linked_user = User.objects.create_user(email="client@example.com", password="test-pass")
        client = Client(
            photographer=self.owner,
            user=linked_user,
            first_name="Avery",
            last_name="Morgan",
            email="client@example.com",
            company="Morgan Co",
            birthday=timezone.localdate(),
            address="1 Main Street",
            client_type=Client.ClientType.BUSINESS,
            preferred_contact_method=Client.ContactMethod.EMAIL,
            tags=["commercial"],
        )
        client.full_clean()

        client.email = ""
        with self.assertRaises(ValidationError) as raised:
            client.full_clean()
        self.assertIn("preferred_contact_method", raised.exception.message_dict)

        client.preferred_contact_method = ""
        client.tags = [""]
        with self.assertRaises(ValidationError) as raised:
            client.full_clean()
        self.assertIn("tags", raised.exception.message_dict)

    def test_client_query_helpers_are_scoped(self):
        now = timezone.now()
        owned = Client.objects.create(photographer=self.owner, first_name="Owned")
        inactive = Client.objects.create(
            photographer=self.owner, first_name="Inactive", status=Client.Status.INACTIVE
        )
        private = Client.objects.create(photographer=self.other, first_name="Private")
        owned_session = ClientSession.objects.create(
            photographer=self.owner,
            client=owned,
            session_type="Portrait",
            starts_at=now + timedelta(days=2),
        )
        ClientSession.objects.create(
            photographer=self.other,
            client=private,
            session_type="Private",
            starts_at=now + timedelta(days=1),
        )
        invoice = ClientInvoice.objects.create(
            photographer=self.owner,
            client=owned,
            total=Decimal("500.00"),
            amount_paid=Decimal("125.00"),
            status=ClientInvoice.Status.PARTIALLY_PAID,
        )
        ClientInvoice.objects.create(
            photographer=self.other,
            client=private,
            total=Decimal("900.00"),
            status=ClientInvoice.Status.SENT,
        )
        activity = ClientActivity.objects.create(
            photographer=self.owner,
            client=owned,
            event_type=ClientActivity.EventType.EMAIL_SENT,
        )
        ClientActivity.objects.create(
            photographer=self.other,
            client=private,
            event_type=ClientActivity.EventType.EMAIL_SENT,
        )

        clients = Client.objects.for_user(self.owner_user)
        self.assertEqual(list(clients.active()), [owned])
        self.assertEqual(list(clients.upcoming_sessions(now)), [owned_session])
        self.assertEqual(list(clients.outstanding_balances()), [invoice])
        self.assertEqual(clients.outstanding_balances().get().balance_due, Decimal("375.00"))
        self.assertEqual(list(clients.recent_activity()), [activity])
        self.assertEqual(clients.total_and_monthly_counts(), {"total": 2, "monthly": 2})
        self.assertNotIn(inactive, clients.active())
