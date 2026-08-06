from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientSession, ClientTask, Lead
from apps.dashboard.access import access_for
from apps.dashboard.crm_overview import build_crm_overview


class CrmOverviewTests(TestCase):
    def studio(self, email, slug):
        user = User.objects.create_user(email=email, password="test", primary_role=User.PrimaryRole.PHOTOGRAPHER)
        profile = PhotographerProfile.objects.create(user=user, business_name=slug, slug=slug, onboarding_completed=True)
        return user, profile

    def test_metrics_and_pipeline_use_only_current_studio(self):
        user, studio = self.studio("owner@example.com", "owner")
        _, other = self.studio("other@example.com", "other")
        today = timezone.localdate()
        Lead.objects.create(photographer=studio, first_name="Due", next_follow_up=today)
        Lead.objects.create(photographer=studio, first_name="Booked", status=Lead.Status.BOOKED)
        Lead.objects.create(photographer=other, first_name="Private", next_follow_up=today)

        overview = build_crm_overview(access_for(user))

        values = {metric["label"]: metric["value"] for metric in overview["crm_metrics"]}
        self.assertEqual(values["Active Leads"], 1)
        self.assertEqual(values["Follow-ups Due"], 1)
        self.assertEqual(values["Lead-to-Booking Conversion"], "50.0%")
        self.assertEqual(sum(stage["count"] for stage in overview["pipeline"]), 2)
        self.assertNotIn("Private", [str(lead) for lead in overview["recent_leads"]])

    def test_conversion_metric_has_an_honest_unavailable_state(self):
        user, _ = self.studio("empty@example.com", "empty")

        overview = build_crm_overview(access_for(user))

        conversion = next(
            metric for metric in overview["crm_metrics"]
            if metric["label"] == "Lead-to-Booking Conversion"
        )
        self.assertTrue(conversion["unavailable"])
        self.assertIsNone(conversion["value"])
        self.assertEqual(conversion["unavailable_text"], "No leads recorded")

    def test_attention_and_task_ordering(self):
        user, studio = self.studio("attention@example.com", "attention")
        today = timezone.localdate()
        recent = Lead.objects.create(photographer=studio, first_name="Recent")
        overdue = Lead.objects.create(photographer=studio, first_name="Overdue", next_follow_up=today - timezone.timedelta(days=1))
        client = Client.objects.create(photographer=studio, first_name="Client")
        future = ClientTask.objects.create(photographer=studio, client=client, title="Future", due_date=today + timezone.timedelta(days=2))
        late = ClientTask.objects.create(photographer=studio, client=client, title="Late", due_date=today - timezone.timedelta(days=2))

        overview = build_crm_overview(access_for(user))

        self.assertEqual(overview["recent_leads"][0].pk, overdue.pk)
        self.assertEqual(list(overview["tasks"])[0].pk, late.pk)
        self.assertNotEqual(recent.pk, overdue.pk)
        self.assertNotEqual(future.pk, late.pk)

    def test_upcoming_sessions_are_studio_scoped(self):
        user, studio = self.studio("sessions@example.com", "sessions")
        _, other = self.studio("private-sessions@example.com", "private-sessions")
        own_client = Client.objects.create(photographer=studio, first_name="Visible")
        private_client = Client.objects.create(photographer=other, first_name="Private")
        starts = timezone.now() + timezone.timedelta(days=1)
        own = ClientSession.objects.create(photographer=studio, client=own_client, session_type="Portrait", starts_at=starts)
        ClientSession.objects.create(photographer=other, client=private_client, session_type="Secret", starts_at=starts)

        overview = build_crm_overview(access_for(user))

        self.assertEqual([session.pk for session in overview["upcoming_sessions"]], [own.pk])
