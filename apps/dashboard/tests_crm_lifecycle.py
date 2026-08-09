from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import PhotographerProfile
from apps.clients.models import Client, ClientActivity, Lead
from apps.dashboard.tests_lead_edit import make_user


class CrmLifecycleRegressionTests(TestCase):
    """Integration coverage for the persisted lead-to-client lifecycle."""

    def setUp(self):
        self.owner = make_user("lifecycle-owner@example.com")
        self.studio = PhotographerProfile.objects.create(
            user=self.owner, slug="lifecycle-studio", onboarding_completed=True
        )
        self.other_owner = make_user("lifecycle-other@example.com")
        self.other_studio = PhotographerProfile.objects.create(
            user=self.other_owner, slug="lifecycle-other", onboarding_completed=True
        )
        self.client.force_login(self.owner)

    def lead_data(self, **overrides):
        data = {
            "first_name": "Marisol",
            "last_name": "O'Connor-Sato",
            "email": "marisol.lifecycle@example.com",
            "phone": "+1 (415) 555-0198",
            "event_type": "Brand portrait",
            "event_date": "2026-11-08",
            "lead_source": "referral",
            "estimated_value": "2800.00",
            "status": Lead.Status.NEW,
            "next_follow_up": "2026-08-20",
            "notes": "Referred by an existing client.",
            "next": reverse("photographer_workspace:leads"),
        }
        data.update(overrides)
        return data

    def test_complete_lifecycle_persists_searches_filters_and_audits(self):
        create = self.client.post(reverse("photographer_workspace:add_lead"), self.lead_data())
        self.assertRedirects(create, reverse("photographer_workspace:leads"))
        lead = Lead.objects.get(email="marisol.lifecycle@example.com")
        created = ClientActivity.objects.get(lead=lead, event_type=ClientActivity.EventType.LEAD_CREATED)
        self.assertEqual(created.actor, self.owner)
        self.assertEqual(created.photographer, self.studio)

        for query in ("Maris", "lifecycle@", "O'Connor"):
            response = self.client.get(reverse("photographer_workspace:leads"), {"q": f"  {query}  "})
            self.assertContains(response, "marisol.lifecycle@example.com")
        self.assertNotContains(
            self.client.get(reverse("photographer_workspace:leads"), {"q": "no-match![]"}),
            "marisol.lifecycle@example.com",
        )
        combined = self.client.get(
            reverse("photographer_workspace:leads"),
            {"status": "new", "source": "referral", "event_type": "Brand portrait"},
        )
        self.assertContains(combined, "marisol.lifecycle@example.com")

        edit = self.lead_data(
            last_name="O'Connor-Sato-Wells", email="marisol.updated@example.com",
            phone="+1 (415) 555-0107", event_type="Editorial portrait",
            lead_source="website", notes="Discovery call completed.",
        )
        self.assertEqual(
            self.client.post(reverse("photographer_workspace:edit_lead", args=[lead.pk]), edit).status_code,
            302,
        )
        lead.refresh_from_db()
        self.assertEqual(lead.notes, "Discovery call completed.")
        refreshed = self.client.get(reverse("photographer_workspace:edit_lead", args=[lead.pk]))
        self.assertContains(refreshed, "marisol.updated@example.com")

        stage_url = reverse("photographer_workspace:update_lead_status", args=[lead.pk])
        self.client.post(stage_url, {"status": Lead.Status.PROPOSAL_SENT, "next": reverse("photographer_workspace:leads")})
        lead.refresh_from_db()
        self.assertEqual(lead.status, Lead.Status.PROPOSAL_SENT)
        self.assertContains(self.client.get(reverse("photographer_workspace:leads"), {"status": "proposal_sent"}), "marisol.updated@example.com")

        convert_url = reverse("photographer_workspace:convert_lead", args=[lead.pk])
        self.assertEqual(self.client.post(convert_url).status_code, 302)
        self.assertEqual(self.client.post(convert_url).status_code, 302)
        lead.refresh_from_db()
        converted = Client.objects.get(converted_lead=lead)
        self.assertEqual(Client.objects.filter(converted_lead=lead).count(), 1)
        self.assertEqual((converted.first_name, converted.last_name, converted.email, converted.phone),
                         (lead.first_name, lead.last_name, lead.email, lead.phone))
        self.assertEqual(lead.status, Lead.Status.BOOKED)
        self.assertEqual(ClientActivity.objects.filter(lead=lead, event_type=ClientActivity.EventType.LEAD_CONVERTED).count(), 1)
        self.assertContains(self.client.get(reverse("photographer_workspace:clients"), {"q": "updated@"}), converted.email)
        detail = self.client.get(reverse("photographer_workspace:client_detail", args=[converted.pk]))
        self.assertContains(detail, converted.email)
        self.assertContains(self.client.get(reverse("photographer_workspace:edit_lead", args=[lead.pk])), "Converted client")

        self.client.logout()
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse("photographer_workspace:leads"), {"terminal": "all"}), converted.email)
        self.assertContains(self.client.get(reverse("photographer_workspace:clients"), {"q": "Marisol"}), converted.email)

    def test_pagination_retains_search_and_filters_and_never_leaks_tenants(self):
        for number in range(13):
            Lead.objects.create(
                photographer=self.studio, first_name=f"Paged {number:02d}",
                email=f"paged-{number}@example.com", lead_source="website",
            )
        private = Lead.objects.create(
            photographer=self.other_studio, first_name="Private Paged",
            email="private-paged@example.com", lead_source="website",
        )
        response = self.client.get(
            reverse("photographer_workspace:leads"),
            {"q": "Paged", "source": "website", "terminal": "all"},
        )
        self.assertEqual(response.context["lead_page"].paginator.count, 13)
        self.assertContains(response, "q=Paged&amp;source=website&amp;terminal=all&amp;page=2")
        page_two = self.client.get(
            reverse("photographer_workspace:leads"),
            {"q": "Paged", "source": "website", "terminal": "all", "page": 2},
        )
        self.assertEqual(page_two.context["lead_page"].number, 2)
        self.assertNotContains(page_two, private.email)

    def test_cross_tenant_direct_lifecycle_attack_paths_return_not_found(self):
        private = Lead.objects.create(
            photographer=self.other_studio, first_name="Tenant Secret", email="tenant-secret@example.com"
        )
        private_client = Client.objects.create(
            photographer=self.other_studio, converted_lead=private,
            first_name=private.first_name, email=private.email,
        )
        self.assertNotContains(self.client.get(reverse("photographer_workspace:leads"), {"q": "Tenant Secret"}), private.email)
        self.assertNotContains(self.client.get(reverse("photographer_workspace:clients"), {"q": "Tenant Secret"}), private.email)
        attacks = (
            ("get", reverse("photographer_workspace:edit_lead", args=[private.pk]), None),
            ("post", reverse("photographer_workspace:edit_lead", args=[private.pk]), self.lead_data()),
            ("post", reverse("photographer_workspace:update_lead_status", args=[private.pk]), {"status": "contacted"}),
            ("post", reverse("photographer_workspace:convert_lead", args=[private.pk]), {}),
            ("get", reverse("photographer_workspace:client_detail", args=[private_client.pk]), None),
            ("post", reverse("photographer_workspace:edit_client", args=[private_client.pk]), {}),
        )
        for method, url, data in attacks:
            response = getattr(self.client, method)(url, data=data) if data is not None else getattr(self.client, method)(url)
            self.assertEqual(response.status_code, 404, url)
        private.refresh_from_db()
        self.assertEqual(private.status, Lead.Status.NEW)
