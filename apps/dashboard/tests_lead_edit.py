from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import ClientProfile, PhotographerProfile, User
from apps.clients.models import ClientActivity, Lead
from apps.dashboard.models import StudioMembership


PASSWORD = "EditLeadPass123!"


def make_user(email, role=User.PrimaryRole.PHOTOGRAPHER):
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        primary_role=role,
        last_active_workspace=(
            User.Workspace.PHOTOGRAPHER
            if role == User.PrimaryRole.PHOTOGRAPHER
            else User.Workspace.CLIENT
        ),
        email_verified=True,
        account_status=User.AccountStatus.ACTIVE,
    )


class LeadEditTests(TestCase):
    def setUp(self):
        self.owner = make_user("lead-owner@example.com")
        self.studio = PhotographerProfile.objects.create(
            user=self.owner,
            slug="lead-edit-studio",
            onboarding_completed=True,
        )
        self.lead = Lead.objects.create(
            photographer=self.studio,
            first_name="Avery",
            last_name="Morgan",
            email="avery@example.com",
            phone="555-0100",
            event_type="Wedding",
            event_date="2026-10-12",
            lead_source="referral",
            estimated_value=Decimal("4200.50"),
            status=Lead.Status.NEW,
            next_follow_up="2026-08-15",
            notes="Original notes",
            tags=["priority", "autumn"],
        )
        self.url = reverse("photographer_workspace:edit_lead", args=[self.lead.pk])

    def edit_data(self, **overrides):
        data = {
            "first_name": "Avery",
            "last_name": "Morgan-Smith",
            "email": "avery.updated@example.com",
            "phone": "555-0199",
            "event_type": "Destination wedding",
            "event_date": "2026-11-14",
            "lead_source": "website",
            "estimated_value": "6250.00",
            "status": Lead.Status.CONTACTED,
            "next_follow_up": "2026-08-20",
            "notes": "Updated after the discovery call.",
        }
        data.update(overrides)
        return data

    def test_successful_edit_persists_supported_fields_and_audit_details(self):
        created_at = self.lead.created_at
        self.client.force_login(self.owner)

        response = self.client.post(self.url, self.edit_data())

        self.assertRedirects(response, reverse("photographer_workspace:leads"))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.last_name, "Morgan-Smith")
        self.assertEqual(self.lead.email, "avery.updated@example.com")
        self.assertEqual(self.lead.phone, "555-0199")
        self.assertEqual(self.lead.event_type, "Destination wedding")
        self.assertEqual(str(self.lead.event_date), "2026-11-14")
        self.assertEqual(self.lead.lead_source, "website")
        self.assertEqual(self.lead.estimated_value, Decimal("6250.00"))
        self.assertEqual(self.lead.status, Lead.Status.CONTACTED)
        self.assertEqual(str(self.lead.next_follow_up), "2026-08-20")
        self.assertEqual(self.lead.notes, "Updated after the discovery call.")
        self.assertEqual(self.lead.tags, ["priority", "autumn"])
        self.assertEqual(self.lead.photographer, self.studio)
        self.assertEqual(self.lead.created_at, created_at)

        activity = ClientActivity.objects.get(
            lead=self.lead, event_type=ClientActivity.EventType.LEAD_UPDATED
        )
        self.assertEqual(activity.photographer, self.studio)
        self.assertEqual(activity.actor, self.owner)
        self.assertIn("email", activity.metadata["changes"])
        self.assertEqual(
            activity.metadata["changes"]["email"],
            {"old": "avery@example.com", "new": "avery.updated@example.com"},
        )
        self.assertIsNotNone(activity.occurred_at)

        refreshed_page = self.client.get(self.url)
        self.assertContains(refreshed_page, "avery.updated@example.com")
        self.assertContains(refreshed_page, "Updated after the discovery call.")

    def test_invalid_edit_does_not_change_record_or_log_activity(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self.url,
            self.edit_data(email="not-an-email", estimated_value="-1"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid email address.")
        self.assertContains(response, "Estimated value cannot be negative.")
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.email, "avery@example.com")
        self.assertEqual(self.lead.estimated_value, Decimal("4200.50"))
        self.assertFalse(
            ClientActivity.objects.filter(
                lead=self.lead, event_type=ClientActivity.EventType.LEAD_UPDATED
            ).exists()
        )

    def test_cross_tenant_url_and_payload_cannot_change_ownership(self):
        other_owner = make_user("other-lead-owner@example.com")
        other_studio = PhotographerProfile.objects.create(
            user=other_owner, slug="other-lead-studio", onboarding_completed=True
        )
        private_lead = Lead.objects.create(
            photographer=other_studio, first_name="Private", email="private@example.com"
        )
        self.client.force_login(self.owner)

        direct = self.client.post(
            reverse("photographer_workspace:edit_lead", args=[private_lead.pk]),
            self.edit_data(),
        )
        self.assertEqual(direct.status_code, 404)
        private_lead.refresh_from_db()
        self.assertEqual(private_lead.email, "private@example.com")

        payload = self.edit_data(
            photographer=other_studio.pk,
            workspace_id=other_studio.pk,
            assigned_user=other_owner.pk,
            tags='["injected"]',
            related_client=private_lead.pk,
        )
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.photographer, self.studio)
        self.assertEqual(self.lead.tags, ["priority", "autumn"])

    def test_access_requires_authenticated_active_workspace_client_permission(self):
        anonymous = self.client.get(self.url)
        self.assertRedirects(
            anonymous,
            f"{reverse('accounts:login')}?next={self.url}",
            fetch_redirect_response=False,
        )

        client_user = make_user("lead-client@example.com", User.PrimaryRole.CLIENT)
        ClientProfile.objects.create(user=client_user, onboarding_completed=True)
        self.client.force_login(client_user)
        self.assertRedirects(
            self.client.get(self.url),
            reverse("clients:dashboard"),
            fetch_redirect_response=False,
        )

        inactive = make_user("inactive-lead-member@example.com")
        StudioMembership.objects.create(
            studio=self.studio,
            user=inactive,
            role=StudioMembership.Role.MANAGER,
            status=StudioMembership.Status.INACTIVE,
        )
        self.client.force_login(inactive)
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_existing_workspace_roles_with_client_access_can_edit(self):
        for role in (StudioMembership.Role.MANAGER, StudioMembership.Role.PHOTOGRAPHER):
            member = make_user(f"edit-{role}@example.com")
            StudioMembership.objects.create(
                studio=self.studio,
                user=member,
                role=role,
                status=StudioMembership.Status.ACTIVE,
            )
            self.client.force_login(member)
            response = self.client.post(
                self.url,
                self.edit_data(notes=f"Updated by {role}"),
            )
            self.assertEqual(response.status_code, 302)
            self.lead.refresh_from_db()
            self.assertEqual(self.lead.notes, f"Updated by {role}")

    def test_repeated_identical_submission_does_not_duplicate_activity(self):
        self.client.force_login(self.owner)
        data = self.edit_data()
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.lead.refresh_from_db()
        updated_at = self.lead.updated_at
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.lead.refresh_from_db()

        self.assertEqual(
            ClientActivity.objects.filter(
                lead=self.lead, event_type=ClientActivity.EventType.LEAD_UPDATED
            ).count(),
            1,
        )
        self.assertEqual(self.lead.updated_at, updated_at)

    def test_edit_endpoint_is_full_post_not_put_or_patch(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.put(self.url, self.edit_data()).status_code, 405)
        self.assertEqual(self.client.patch(self.url, self.edit_data()).status_code, 405)
