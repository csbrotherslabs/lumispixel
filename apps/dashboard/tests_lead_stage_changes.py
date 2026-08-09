from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import PhotographerProfile
from apps.clients.models import Client, ClientActivity, Lead
from apps.dashboard.tests_lead_edit import make_user


class LeadStageChangeTests(TestCase):
    def setUp(self):
        self.owner = make_user("stage-owner@example.com")
        self.studio = PhotographerProfile.objects.create(
            user=self.owner, slug="stage-studio", onboarding_completed=True
        )
        self.lead = Lead.objects.create(
            photographer=self.studio,
            first_name="Pipeline",
            email="pipeline@example.com",
            estimated_value="2500.00",
        )
        self.url = reverse(
            "photographer_workspace:update_lead_status", args=[self.lead.pk]
        )
        self.client.force_login(self.owner)

    def test_valid_change_persists_updates_views_metrics_and_filter(self):
        response = self.client.post(
            self.url,
            {"status": Lead.Status.CONTACTED, "next": reverse("photographer_workspace:leads")},
        )

        self.assertRedirects(response, reverse("photographer_workspace:leads"))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, Lead.Status.CONTACTED)
        self.assertContains(self.client.get(reverse("photographer_workspace:leads")), "Contacted")
        filtered = self.client.get(
            reverse("photographer_workspace:leads"), {"status": Lead.Status.CONTACTED}
        )
        self.assertContains(filtered, "Pipeline")
        self.assertNotContains(
            self.client.get(reverse("photographer_workspace:leads"), {"status": Lead.Status.NEW}),
            "pipeline@example.com",
        )
        crm = self.client.get(reverse("photographer_workspace:crm"))
        contacted = next(item for item in crm.context["pipeline"] if item["key"] == Lead.Status.CONTACTED)
        self.assertEqual(contacted["count"], 1)

        activity = ClientActivity.objects.get(
            lead=self.lead, event_type=ClientActivity.EventType.STAGE_CHANGED
        )
        self.assertEqual(activity.actor, self.owner)
        self.assertEqual(activity.photographer, self.studio)
        self.assertEqual(activity.metadata, {"from": Lead.Status.NEW, "to": Lead.Status.CONTACTED})
        self.assertEqual(activity.description, "Lead stage changed from New to Contacted.")

    def test_invalid_and_unchanged_values_do_not_persist_or_log(self):
        self.client.post(self.url, {"status": "arbitrary-stage"})
        self.client.post(self.url, {"status": Lead.Status.NEW})

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, Lead.Status.NEW)
        self.assertFalse(ClientActivity.objects.filter(lead=self.lead).exists())

    def test_cross_workspace_and_anonymous_requests_cannot_change_stage(self):
        other_owner = make_user("other-stage-owner@example.com")
        other_studio = PhotographerProfile.objects.create(
            user=other_owner, slug="other-stage-studio", onboarding_completed=True
        )
        private_lead = Lead.objects.create(
            photographer=other_studio, first_name="Private", email="private-stage@example.com"
        )
        private_url = reverse(
            "photographer_workspace:update_lead_status", args=[private_lead.pk]
        )

        self.assertEqual(
            self.client.post(private_url, {"status": Lead.Status.CONTACTED}).status_code,
            404,
        )
        self.client.logout()
        response = self.client.post(self.url, {"status": Lead.Status.CONTACTED})
        self.assertEqual(response.status_code, 302)
        self.lead.refresh_from_db()
        private_lead.refresh_from_db()
        self.assertEqual(self.lead.status, Lead.Status.NEW)
        self.assertEqual(private_lead.status, Lead.Status.NEW)

    def test_bulk_change_skips_unchanged_stage_and_records_actor(self):
        second = Lead.objects.create(
            photographer=self.studio, first_name="Second", status=Lead.Status.CONTACTED
        )
        self.client.post(
            reverse("photographer_workspace:bulk_update_leads"),
            {
                "lead_ids": [self.lead.pk, second.pk],
                "action": Lead.Status.CONTACTED,
            },
        )

        self.assertEqual(
            ClientActivity.objects.filter(event_type=ClientActivity.EventType.STAGE_CHANGED).count(),
            1,
        )
        self.assertEqual(ClientActivity.objects.get().actor, self.owner)

    def test_edit_to_booked_creates_client_and_edit_to_lost_requires_reason_flow(self):
        edit_url = reverse("photographer_workspace:edit_lead", args=[self.lead.pk])
        data = {
            "first_name": self.lead.first_name,
            "last_name": "",
            "email": self.lead.email,
            "phone": "",
            "event_type": "",
            "event_date": "",
            "lead_source": "",
            "estimated_value": "2500.00",
            "status": Lead.Status.BOOKED,
            "next_follow_up": "",
            "notes": "",
        }
        self.assertEqual(self.client.post(edit_url, data).status_code, 302)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, Lead.Status.BOOKED)
        self.assertTrue(Client.objects.filter(converted_lead=self.lead).exists())

        another = Lead.objects.create(
            photographer=self.studio, first_name="Loss", email="loss@example.com"
        )
        data.update({"first_name": "Loss", "email": "loss@example.com", "status": Lead.Status.LOST})
        response = self.client.post(
            reverse("photographer_workspace:edit_lead", args=[another.pk]), data
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Use Mark lost")
        another.refresh_from_db()
        self.assertEqual(another.status, Lead.Status.NEW)
