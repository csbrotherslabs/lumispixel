from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import PhotographerProfile
from apps.clients.models import Client, ClientActivity, ClientNote, Lead
from apps.dashboard.models import StudioMembership
from apps.dashboard.tests_lead_edit import make_user


class ClientEditTests(TestCase):
    def setUp(self):
        self.owner = make_user("client-edit-owner@example.com")
        self.studio = PhotographerProfile.objects.create(
            user=self.owner, slug="client-edit-studio", onboarding_completed=True
        )
        self.lead = Lead.objects.create(
            photographer=self.studio, first_name="Original", email="lead@example.com"
        )
        self.record = Client.objects.create(
            photographer=self.studio,
            converted_lead=self.lead,
            first_name="Avery",
            last_name="Morgan",
            email="avery@example.com",
            phone="555-0100",
            company="Original Company",
            address="10 Main St\nBoston\nMA\n02110\nUS",
            lead_source="referral",
            tags=["vip", "portrait"],
            client_type=Client.ClientType.INDIVIDUAL,
            preferred_contact_method=Client.ContactMethod.EMAIL,
        )
        self.url = reverse("photographer_workspace:edit_client", args=[self.record.pk])

    def form_data(self, **overrides):
        data = {
            "first_name": "Avery",
            "last_name": "Morgan-Wells",
            "email": "avery.updated@example.com",
            "phone": "555-0199",
            "company": "Updated Company",
            "address": "20 State St",
            "city": "Cambridge",
            "state_province": "MA",
            "postal_code": "02139",
            "country": "US",
            "birthday": "1990-06-15",
            "status": Client.Status.ACTIVE,
            "client_type": Client.ClientType.BUSINESS,
            "lead_source": "website",
            "preferred_contact_method": Client.ContactMethod.EMAIL,
            "tags_input": "vip, commercial",
            "notes": "Prefers morning calls.",
        }
        data.update(overrides)
        return data

    def test_successful_update_persists_fields_preserves_protected_data_and_audits(self):
        self.client.force_login(self.owner)
        edit_page = self.client.get(self.url)
        self.assertContains(edit_page, 'class="workspace-form-page lp-container lp-edit-client lp-clients-main-width"')
        self.assertContains(edit_page, "Edit client")
        self.assertContains(edit_page, str(self.record))
        self.assertContains(edit_page, reverse("photographer_workspace:client_detail", args=[self.record.pk]))
        self.assertEqual(edit_page.content.decode().count("<h1"), 1)
        created_at = self.record.created_at
        response = self.client.post(
            self.url,
            self.form_data(
                photographer="999999", converted_lead="999999", user="999999",
                created_at="2000-01-01T00:00:00Z",
            ),
        )
        self.assertRedirects(
            response, reverse("photographer_workspace:client_detail", args=[self.record.pk])
        )
        self.record.refresh_from_db()
        self.assertEqual(self.record.last_name, "Morgan-Wells")
        self.assertEqual(self.record.email, "avery.updated@example.com")
        self.assertEqual(self.record.company, "Updated Company")
        self.assertEqual(self.record.address, "20 State St\nCambridge\nMA\n02139\nUS")
        self.assertEqual(self.record.lead_source, "website")
        self.assertEqual(self.record.tags, ["vip", "commercial"])
        self.assertEqual(self.record.photographer, self.studio)
        self.assertEqual(self.record.converted_lead, self.lead)
        self.assertEqual(self.record.created_at, created_at)
        self.assertEqual(Client.objects.count(), 1)
        self.assertEqual(ClientNote.objects.get(client=self.record).content, "Prefers morning calls.")
        activity = ClientActivity.objects.get(
            client=self.record, event_type=ClientActivity.EventType.CLIENT_UPDATED
        )
        self.assertEqual(activity.actor, self.owner)
        self.assertEqual(activity.photographer, self.studio)
        self.assertEqual(
            activity.metadata["changes"]["email"],
            {"old": "avery@example.com", "new": "avery.updated@example.com"},
        )
        self.assertContains(self.client.get(self.url), "avery.updated@example.com")
        self.assertContains(self.client.get(self.url), "website", html=False)
        self.assertContains(
            self.client.get(reverse("photographer_workspace:client_detail", args=[self.record.pk])),
            "avery.updated@example.com",
        )

    def test_validation_failure_and_duplicate_email_do_not_mutate(self):
        duplicate = Client.objects.create(
            photographer=self.studio, first_name="Duplicate", email="taken@example.com"
        )
        self.client.force_login(self.owner)
        response = self.client.post(self.url, self.form_data(email="TAKEN@example.com"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A client with this email address already exists")
        self.record.refresh_from_db()
        self.assertEqual(self.record.email, "avery@example.com")
        self.assertEqual(Client.objects.count(), 2)
        self.assertTrue(Client.objects.filter(pk=duplicate.pk).exists())
        self.assertFalse(ClientActivity.objects.filter(client=self.record).exists())

        response = self.client.post(self.url, self.form_data(email="bad-email"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid email address")
        self.record.refresh_from_db()
        self.assertEqual(self.record.email, "avery@example.com")

    def test_unchanged_resubmission_does_not_duplicate_activity_notes_or_clients(self):
        self.client.force_login(self.owner)
        self.client.post(self.url, self.form_data())
        self.record.refresh_from_db()
        repeated_data = self.form_data()
        self.client.post(self.url, repeated_data)
        self.assertEqual(Client.objects.filter(pk=self.record.pk).count(), 1)
        self.assertEqual(ClientNote.objects.filter(client=self.record).count(), 1)
        self.assertEqual(
            ClientActivity.objects.filter(
                client=self.record, event_type=ClientActivity.EventType.CLIENT_UPDATED
            ).count(),
            1,
        )

    def test_cross_workspace_url_and_duplicate_identity_are_isolated(self):
        other_owner = make_user("client-edit-other@example.com")
        other_studio = PhotographerProfile.objects.create(
            user=other_owner, slug="client-edit-other", onboarding_completed=True
        )
        private = Client.objects.create(
            photographer=other_studio, first_name="Private", email="private@example.com"
        )
        # An identity in a different workspace does not create a false duplicate.
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.url, self.form_data(email=private.email)).status_code, 302)
        response = self.client.post(
            reverse("photographer_workspace:edit_client", args=[private.pk]), self.form_data()
        )
        self.assertEqual(response.status_code, 404)
        private.refresh_from_db()
        self.assertEqual(private.email, "private@example.com")

    def test_permissions_require_authentication_and_an_explicit_assignment(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        member_user = make_user("assigned-client-editor@example.com")
        membership = StudioMembership.objects.create(
            studio=self.studio,
            user=member_user,
            role=StudioMembership.Role.PHOTOGRAPHER,
            status=StudioMembership.Status.ACTIVE,
        )
        self.client.force_login(member_user)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.record.assigned_members.add(membership)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.post(self.url, self.form_data()).status_code, 302)
