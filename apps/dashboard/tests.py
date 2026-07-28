from django.core.management import call_command
from django.test import Client as TestClient, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import ClientProfile, PhotographerProfile, User
from apps.clients.models import Client, ClientActivity, ClientInvoice, ClientNote, ClientSession, ClientTask, Lead
from apps.dashboard.views import WORKSPACE_MODULES


def make_user(email, role=User.PrimaryRole.PHOTOGRAPHER):
    return User.objects.create_user(email=email, password="pass12345", primary_role=role, last_active_workspace=User.Workspace.PHOTOGRAPHER if role == User.PrimaryRole.PHOTOGRAPHER else User.Workspace.CLIENT, email_verified=True, account_status=User.AccountStatus.ACTIVE)


class PhotographerWorkspaceTests(TestCase):
    def make_photographer(self, completed=True, **profile_kwargs):
        user = make_user(profile_kwargs.pop("email", "photo@example.com"))
        profile = PhotographerProfile.objects.create(user=user, slug=profile_kwargs.pop("slug", "photo"), onboarding_completed=completed, **profile_kwargs)
        return user, profile

    def test_anonymous_client_and_incomplete_access_rules(self):
        url = reverse("photographer_workspace:dashboard")
        self.assertRedirects(self.client.get(url), f"{reverse('accounts:login')}?next={url}", fetch_redirect_response=False)
        client_user = make_user("client@example.com", User.PrimaryRole.CLIENT)
        ClientProfile.objects.create(user=client_user, onboarding_completed=True)
        self.client.force_login(client_user)
        self.assertRedirects(self.client.get(url), reverse("clients:dashboard"), fetch_redirect_response=False)
        self.client.logout()
        incomplete, _ = self.make_photographer(False, email="incomplete@example.com", slug="incomplete")
        self.client.force_login(incomplete)
        self.assertRedirects(self.client.get(url), reverse("photographers:setup-dashboard"), fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse("photographer_workspace:galleries")), reverse("photographers:setup-dashboard"), fetch_redirect_response=False)

    def test_completed_photographer_dashboard_and_post_login_destination(self):
        user, _ = self.make_photographer(True, business_name="Lumis Studio", display_name="Alex Lens", website_theme=PhotographerProfile.WebsiteTheme.MODERN_STUDIO)
        user.first_name = "Alex"
        user.save(update_fields=["first_name"])
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse("accounts:post-login-redirect")), reverse("photographer_workspace:dashboard"), fetch_redirect_response=False)
        response = self.client.get(reverse("photographer_workspace:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="dashboard-heading"')
        self.assertNotContains(response, '<h2>Dashboard</h2>', html=True)
        self.assertContains(response, "Good ")
        self.assertContains(response, "Alex.")
        self.assertContains(response, "Here’s what’s happening with your business today.")
        self.assertContains(response, "Revenue This Month")
        self.assertContains(response, "Active Clients")
        self.assertContains(response, "Upcoming Bookings")
        self.assertContains(response, "Today’s Schedule")
        self.assertContains(response, "Recent Activity")
        self.assertContains(response, "Business Snapshot")
        self.assertContains(response, "Explore Business Tools")
        self.assertNotContains(response, "Your Website Preview")
        self.assertNotContains(response, "Help and Resources")
        self.assertContains(response, "0")
        self.assertContains(response, f'href="{reverse("core:index")}" aria-label="LumisPixel home"')

    def test_missing_images_and_invalid_theme_fallback_do_not_error(self):
        user, profile = self.make_photographer(True, email="fallback@example.com", slug="fallback", display_name="Fallback Photo")
        PhotographerProfile.objects.filter(pk=profile.pk).update(website_theme="legacy")
        self.client.force_login(user)
        response = self.client.get(reverse("photographer_workspace:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fallback Photo")
        self.assertContains(response, "Dashboard")

    def test_navigation_urls_and_placeholders_resolve(self):
        user, _ = self.make_photographer(True, email="nav@example.com", slug="nav")
        self.client.force_login(user)
        for module in WORKSPACE_MODULES:
            url = reverse(f"photographer_workspace:{module['url_name']}")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, module["title"])
            if module["key"] not in {"dashboard", "crm", "leads", "clients"}:
                self.assertContains(response, "Back to Dashboard")

    def test_clients_workspace_uses_scoped_data_and_directory_controls(self):
        user, profile = self.make_photographer(True, email="directory@example.com", slug="directory")
        _, other = self.make_photographer(True, email="other-directory@example.com", slug="other-directory")
        visible = Client.objects.create(photographer=profile, first_name="Avery", last_name="Stone", email="avery@example.com", tags=["VIP"], client_type=Client.ClientType.INDIVIDUAL)
        ClientInvoice.objects.create(photographer=profile, client=visible, total="900.00", amount_paid="250.00", status=ClientInvoice.Status.SENT)
        Client.objects.create(photographer=other, first_name="Private", last_name="Record")
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:clients"), {"tag": "VIP"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Manage client relationships, projects, payments, and galleries.")
        self.assertContains(response, "Avery Stone")
        self.assertContains(response, "USD 650.00")
        self.assertNotContains(response, "Private Record")
        self.assertContains(response, 'data-client-view="list"')
        self.assertContains(response, 'data-client-view="grid"')

    def test_client_detail_actions_tabs_alerts_and_isolation(self):
        user, profile = self.make_photographer(True, email="detail@example.com", slug="detail")
        _, other = self.make_photographer(True, email="private-detail@example.com", slug="private-detail")
        client = Client.objects.create(photographer=profile, first_name="Avery", last_name="Stone", email="avery@example.com", tags=["VIP"], preferred_contact_method=Client.ContactMethod.EMAIL)
        private = Client.objects.create(photographer=other, first_name="Private", last_name="Client")
        ClientInvoice.objects.create(photographer=profile, client=client, total="500", amount_paid="100", status=ClientInvoice.Status.SENT, due_date="2020-01-01")
        ClientSession.objects.create(photographer=profile, client=client, session_type="Portrait", starts_at=timezone.now() + timezone.timedelta(days=2), status=ClientSession.Status.CONFIRMED)
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:client_detail", args=[client.pk]))
        self.assertContains(response, "Contact details")
        self.assertContains(response, "Outstanding balance")
        self.assertContains(response, "Overdue invoices")
        self.assertContains(response, "Unsigned contracts")
        self.assertContains(response, "Galleries awaiting delivery")
        self.assertContains(response, "USD 400.00")
        self.assertEqual(self.client.get(reverse("photographer_workspace:client_detail", args=[private.pk])).status_code, 404)

        self.client.post(reverse("photographer_workspace:add_client_note", args=[client.pk]), {"content": "Prefers mornings"})
        self.client.post(reverse("photographer_workspace:add_client_task", args=[client.pk]), {"title": "Send guide", "priority": "high"})
        self.assertTrue(ClientNote.objects.filter(client=client, content="Prefers mornings").exists())
        self.assertTrue(ClientTask.objects.filter(client=client, title="Send guide").exists())
        self.client.post(reverse("photographer_workspace:client_archive_restore", args=[client.pk]))
        client.refresh_from_db()
        self.assertEqual(client.status, Client.Status.ARCHIVED)
        self.client.post(reverse("photographer_workspace:client_archive_restore", args=[client.pk]))
        client.refresh_from_db()
        self.assertEqual(client.status, Client.Status.ACTIVE)
        self.assertTrue(ClientActivity.objects.filter(client=client, event_type=ClientActivity.EventType.CLIENT_RESTORED).exists())

    def test_client_mutations_require_csrf(self):
        user, profile = self.make_photographer(True, email="client-csrf@example.com", slug="client-csrf")
        client = Client.objects.create(photographer=profile, first_name="Protected", email="protected@example.com")
        csrf_client = TestClient(enforce_csrf_checks=True)
        csrf_client.force_login(user)
        self.assertEqual(csrf_client.post(reverse("photographer_workspace:client_archive_restore", args=[client.pk])).status_code, 403)
        client.refresh_from_db()
        self.assertEqual(client.status, Client.Status.ACTIVE)

    def test_crm_dashboard_uses_only_logged_in_photographers_records(self):
        user, profile = self.make_photographer(True, email="crm@example.com", slug="crm")
        other_user, other = self.make_photographer(True, email="other-crm@example.com", slug="other-crm")
        Lead.objects.create(photographer=profile, first_name="Visible", status=Lead.Status.NEW)
        Lead.objects.create(photographer=other, first_name="Private", status=Lead.Status.NEW)
        client = Client.objects.create(photographer=profile, first_name="Taylor")
        ClientInvoice.objects.create(photographer=profile, client=client, total="500.00", amount_paid="125.00", status=ClientInvoice.Status.SENT)
        other_client = Client.objects.create(photographer=other, first_name="Other")
        ClientInvoice.objects.create(photographer=other, client=other_client, total="900.00", status=ClientInvoice.Status.SENT)

        self.client.force_login(user)
        response = self.client.get(reverse("photographer_workspace:crm"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Manage leads, clients, tasks, and upcoming activity.")
        self.assertContains(response, "Visible")
        self.assertNotContains(response, "Private")
        self.assertContains(response, "USD 375.00")
        self.assertContains(response, "?status=new")

    def test_active_navigation_item_is_correct(self):
        user, _ = self.make_photographer(True, email="active@example.com", slug="active")
        self.client.force_login(user)
        response = self.client.get(reverse("photographer_workspace:analytics"))
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, "Analytics")

    def test_grouped_navigation_and_profile_menu(self):
        user, _ = self.make_photographer(True, email="grouped@example.com", slug="grouped")
        user.first_name = "Avery"
        user.last_name = "Stone"
        user.save(update_fields=["first_name", "last_name"])
        self.client.force_login(user)
        response = self.client.get(reverse("photographer_workspace:crm"))
        self.assertContains(response, "Business Growth")
        self.assertContains(response, 'aria-controls="nav-group-1"')
        self.assertContains(response, 'aria-label="Clients" data-tooltip="Clients"')
        self.assertContains(response, 'href="/photographer/workspace/leads/"')
        self.assertContains(response, "Avery Stone")
        self.assertContains(response, "Photographer")
        self.assertContains(response, "Business Settings")
        self.assertContains(response, "Sign Out")

    def test_client_cannot_access_module_url(self):
        client_user = make_user("client-module@example.com", User.PrimaryRole.CLIENT)
        ClientProfile.objects.create(user=client_user, onboarding_completed=True)
        self.client.force_login(client_user)
        self.assertRedirects(self.client.get(reverse("photographer_workspace:orders")), reverse("clients:dashboard"), fetch_redirect_response=False)

    def test_system_checks_pass(self):
        call_command("check")

    def test_crm_create_complete_and_convert_workflow(self):
        user, profile = self.make_photographer(True, email="workflow@example.com", slug="workflow")
        self.client.force_login(user)
        response = self.client.post(reverse("photographer_workspace:add_lead"), {
            "first_name": "Jordan", "last_name": "Lee", "email": "jordan@example.com",
        })
        self.assertRedirects(response, reverse("photographer_workspace:crm"))
        lead = Lead.objects.get(photographer=profile, email="jordan@example.com")
        self.assertTrue(ClientActivity.objects.filter(lead=lead, event_type=ClientActivity.EventType.LEAD_CREATED).exists())

        response = self.client.post(reverse("photographer_workspace:create_task"), {
            "title": "Call Jordan", "priority": ClientTask.Priority.HIGH, "lead": lead.pk,
        })
        self.assertRedirects(response, reverse("photographer_workspace:crm"))
        task = ClientTask.objects.get(photographer=profile)
        self.client.post(reverse("photographer_workspace:complete_task", args=[task.pk]))
        task.refresh_from_db()
        self.assertEqual(task.status, ClientTask.Status.COMPLETED)

        self.client.post(reverse("photographer_workspace:convert_lead", args=[lead.pk]))
        lead.refresh_from_db()
        converted = Client.objects.get(converted_lead=lead)
        self.assertEqual(converted.photographer, profile)
        self.assertEqual(lead.status, Lead.Status.BOOKED)
        self.assertTrue(ClientActivity.objects.filter(lead=lead, client=converted, event_type=ClientActivity.EventType.LEAD_CONVERTED).exists())
        self.client.post(reverse("photographer_workspace:convert_lead", args=[lead.pk]))
        self.assertEqual(Client.objects.filter(converted_lead=lead).count(), 1)

    def test_crm_client_creation_and_ownership_protection(self):
        user, profile = self.make_photographer(True, email="create@example.com", slug="create")
        other_user, other = self.make_photographer(True, email="private@example.com", slug="private")
        private_task = ClientTask.objects.create(photographer=other, lead=Lead.objects.create(photographer=other, first_name="Private"), title="Private")
        self.client.force_login(user)
        self.client.post(reverse("photographer_workspace:add_client"), {"first_name": "Sam", "email": "sam@example.com", "status": Client.Status.ACTIVE})
        self.assertTrue(Client.objects.filter(photographer=profile, email="sam@example.com").exists())
        self.assertEqual(self.client.post(reverse("photographer_workspace:complete_task", args=[private_task.pk])).status_code, 404)
        private_task.refresh_from_db()
        self.assertEqual(private_task.status, ClientTask.Status.OPEN)

    def test_add_client_form_renders_crud_system_and_saves_extended_details(self):
        user, profile = self.make_photographer(True, email="form@example.com", slug="form")
        self.client.force_login(user)
        response = self.client.get(reverse("photographer_workspace:add_client"))
        self.assertContains(response, 'class="workspace-form-page"')
        self.assertContains(response, 'class="form-section-card"')
        self.assertContains(response, 'data-upload-dropzone')
        self.assertContains(response, 'data-submit-button')
        self.assertContains(response, '<h1 id="workspace-page-title">Add Client</h1>', count=1, html=True)

        response = self.client.post(reverse("photographer_workspace:add_client"), {
            "first_name": "Avery", "email": "avery@example.com", "status": Client.Status.ACTIVE,
            "address": "10 Main Street", "city": "Portland", "state_province": "Oregon",
            "postal_code": "97205", "country": "United States", "tags_input": "VIP,Portrait",
            "notes": "Prefers morning sessions.",
        })
        self.assertRedirects(response, reverse("photographer_workspace:crm"))
        client = Client.objects.get(photographer=profile, email="avery@example.com")
        self.assertEqual(client.address, "10 Main Street\nPortland\nOregon\n97205\nUnited States")
        self.assertEqual(client.tags, ["VIP", "Portrait"])
        self.assertEqual(client.notes.get().content, "Prefers morning sessions.")

    def test_add_lead_form_uses_crud_design_system(self):
        user, _ = self.make_photographer(True, email="lead-form@example.com", slug="lead-form")
        self.client.force_login(user)
        response = self.client.get(reverse("photographer_workspace:add_lead"))
        self.assertContains(response, 'class="workspace-form-page"')
        self.assertContains(response, "Contact Information")
        self.assertContains(response, "Inquiry Details")
        self.assertContains(response, 'aria-label="Lead setup help"')
        self.assertContains(response, 'data-submit-button')
        self.assertContains(response, "Save Lead")
        self.assertContains(response, '<h1 id="workspace-page-title">Add Lead</h1>', count=1, html=True)

    def test_crm_mutations_require_authentication_and_post(self):
        user, profile = self.make_photographer(True, email="secure@example.com", slug="secure")
        lead = Lead.objects.create(photographer=profile, first_name="Secure")
        url = reverse("photographer_workspace:convert_lead", args=[lead.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(user)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.logout()
        self.client.post(url)
        self.assertFalse(Client.objects.filter(converted_lead=lead).exists())

    def test_leads_workspace_uses_scoped_real_data_and_metrics(self):
        user, profile = self.make_photographer(True, email="pipeline@example.com", slug="pipeline")
        _, other = self.make_photographer(True, email="other-pipeline@example.com", slug="other-pipeline")
        Lead.objects.create(photographer=profile, first_name="Morgan", last_name="Ray", event_type="Wedding", estimated_value="2400", lead_source="Referral")
        Lead.objects.create(photographer=profile, first_name="Casey", status=Lead.Status.BOOKED, estimated_value="1600")
        Lead.objects.create(photographer=other, first_name="Private", estimated_value="9000")
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:leads"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Track inquiries and move prospects toward booking.")
        self.assertContains(response, "Morgan Ray")
        self.assertNotContains(response, "Private")
        self.assertContains(response, "USD 4,000")
        self.assertContains(response, "50.0%")
        self.assertContains(response, 'data-lead-view="board"')
        self.assertContains(response, 'data-stage="proposal_sent"')

    def test_lead_stage_and_bulk_updates_are_scoped(self):
        user, profile = self.make_photographer(True, email="move@example.com", slug="move")
        _, other = self.make_photographer(True, email="other-move@example.com", slug="other-move")
        own = Lead.objects.create(photographer=profile, first_name="Move Me")
        private = Lead.objects.create(photographer=other, first_name="Do Not Move")
        self.client.force_login(user)
        self.client.post(reverse("photographer_workspace:update_lead_status", args=[own.pk]), {"status": Lead.Status.CONTACTED, "next": reverse("photographer_workspace:leads")})
        self.client.post(reverse("photographer_workspace:bulk_update_leads"), {"lead_ids": [own.pk, private.pk], "action": Lead.Status.CONSULTATION})
        own.refresh_from_db()
        private.refresh_from_db()
        self.assertEqual(own.status, Lead.Status.CONSULTATION)
        self.assertEqual(private.status, Lead.Status.NEW)

    def test_lead_actions_validate_log_and_enforce_ownership(self):
        user, profile = self.make_photographer(True, email="actions@example.com", slug="actions")
        _, other = self.make_photographer(True, email="other-actions@example.com", slug="other-actions")
        lead = Lead.objects.create(photographer=profile, first_name="Action", email="action@example.com")
        private = Lead.objects.create(photographer=other, first_name="Private", email="private@example.com")
        self.client.force_login(user)

        self.assertEqual(self.client.post(reverse("photographer_workspace:add_lead_note", args=[private.pk]), {"note": "No access"}).status_code, 404)
        self.client.post(reverse("photographer_workspace:add_lead_note", args=[lead.pk]), {"note": "Prefers afternoons"})
        self.client.post(reverse("photographer_workspace:create_lead_follow_up", args=[lead.pk]), {"title": "Call lead", "due_date": "2026-08-01", "priority": "high"})
        self.client.post(reverse("photographer_workspace:mark_lead_lost", args=[lead.pk]), {"reason": ""})
        lead.refresh_from_db()
        self.assertEqual(lead.status, Lead.Status.NEW)
        self.assertIn("Prefers afternoons", lead.notes)
        self.assertEqual(lead.tasks.get().title, "Call lead")
        self.assertTrue(ClientActivity.objects.filter(lead=lead, event_type=ClientActivity.EventType.NOTE_ADDED).exists())
        self.assertTrue(ClientActivity.objects.filter(lead=lead, event_type=ClientActivity.EventType.FOLLOW_UP_CREATED).exists())

        self.client.post(reverse("photographer_workspace:mark_lead_lost", args=[lead.pk]), {"reason": "Budget changed"})
        lead.refresh_from_db()
        self.assertEqual((lead.status, lead.lost_reason), (Lead.Status.LOST, "Budget changed"))
        self.client.post(reverse("photographer_workspace:archive_lead", args=[lead.pk]))
        lead.refresh_from_db()
        self.assertIsNotNone(lead.archived_at)
        self.assertNotContains(self.client.get(reverse("photographer_workspace:leads")), "action@example.com")

    def test_lead_mutations_require_csrf(self):
        user, profile = self.make_photographer(True, email="csrf@example.com", slug="csrf")
        lead = Lead.objects.create(photographer=profile, first_name="Protected", email="protected@example.com")
        csrf_client = TestClient(enforce_csrf_checks=True)
        csrf_client.force_login(user)
        response = csrf_client.post(reverse("photographer_workspace:mark_lead_booked", args=[lead.pk]))
        self.assertEqual(response.status_code, 403)
        lead.refresh_from_db()
        self.assertEqual(lead.status, Lead.Status.NEW)
