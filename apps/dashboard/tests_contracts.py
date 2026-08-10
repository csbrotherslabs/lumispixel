from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.contracts import create_contract_from_template
from apps.clients.models import Client, ClientSession, Contract, ContractEvent, ContractTemplate
from apps.dashboard.models import StudioMembership
from apps.clients.contracts import render_merge_fields


class ContractWorkflowTests(TestCase):
    def make_studio(self, email):
        user = User.objects.create_user(email=email, password="pass12345")
        user.account_status = User.AccountStatus.ACTIVE
        user.primary_role = User.PrimaryRole.PHOTOGRAPHER
        user.save()
        studio = PhotographerProfile.objects.create(user=user, onboarding_completed=True)
        client = Client.objects.create(photographer=studio, first_name="Maya", last_name="Cole")
        booking = ClientSession.objects.create(
            photographer=studio, client=client, session_type="Portrait",
            starts_at=timezone.now() + timezone.timedelta(days=5),
        )
        template = ContractTemplate.objects.create(
            photographer=studio, name="Portrait standard", title="Portrait Agreement",
            content="Original persisted terms", created_by=user,
        )
        return user, studio, client, booking, template

    def setUp(self):
        self.owner, self.studio, self.crm_client, self.booking, self.template = self.make_studio(
            "contract-owner@example.com"
        )

    def test_template_and_contract_snapshot_are_persisted(self):
        contract = create_contract_from_template(
            booking=self.booking, template=self.template, actor=self.owner,
        )
        self.assertEqual(contract.client, self.booking.client)
        self.assertEqual(contract.photographer, self.studio)
        self.assertEqual(contract.status, Contract.Status.DRAFT)
        self.assertEqual(contract.content, "Original persisted terms")
        self.assertEqual(contract.version, self.template.version)
        self.assertTrue(Contract.objects.filter(pk=contract.pk).exists())
        self.assertTrue(contract.events.filter(event_type=ContractEvent.EventType.CREATED).exists())

        self.template.content = "Updated future terms"
        self.template.version = 2
        self.template.save()
        contract.refresh_from_db()
        self.assertEqual(contract.content, "Original persisted terms")
        self.assertEqual(contract.version, 1)

    def test_contract_relationship_validation_rejects_mismatches(self):
        _other_owner, other_studio, other_client, _other_booking, other_template = self.make_studio(
            "validation-other@example.com"
        )
        contract = Contract(
            photographer=self.studio, booking=self.booking, client=other_client,
            template=other_template, title="Invalid", content="Terms",
        )
        with self.assertRaises(ValidationError) as error:
            contract.full_clean()
        self.assertIn("client", error.exception.message_dict)
        self.assertIn("template", error.exception.message_dict)
        self.assertNotEqual(other_studio, self.studio)

    def test_owner_creates_draft_from_booking_and_can_reopen_it(self):
        self.client.force_login(self.owner)
        create_url = reverse("photographer_workspace:contract_create", args=[self.booking.pk])
        response = self.client.post(create_url, {"template": self.template.pk})
        contract = Contract.objects.get()
        self.assertRedirects(response, reverse("photographer_workspace:contract_detail", args=[contract.pk]))
        detail = self.client.get(response.url)
        self.assertContains(detail, "Portrait Agreement")
        self.assertContains(detail, "Original persisted terms")
        booking_page = self.client.get(
            reverse("photographer_workspace:booking_detail", args=[self.booking.pk]), {"tab": "contract"},
        )
        self.assertContains(booking_page, "Draft")
        self.assertContains(booking_page, reverse("photographer_workspace:contract_detail", args=[contract.pk]))

    def test_cross_workspace_booking_template_and_contract_ids_are_hidden(self):
        other_owner, _other_studio, _other_client, other_booking, other_template = self.make_studio(
            "contract-other@example.com"
        )
        private_contract = create_contract_from_template(
            booking=other_booking, template=other_template, actor=other_owner,
        )
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.get(reverse("photographer_workspace:contract_create", args=[other_booking.pk])).status_code,
            404,
        )
        response = self.client.post(
            reverse("photographer_workspace:contract_create", args=[self.booking.pk]),
            {"template": other_template.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        self.assertEqual(Contract.objects.filter(photographer=self.studio).count(), 0)
        self.assertEqual(
            self.client.get(reverse("photographer_workspace:contract_detail", args=[private_contract.pk])).status_code,
            404,
        )

    def test_manager_and_assigned_photographer_can_access_but_unassigned_cannot(self):
        manager = User.objects.create_user(email="manager-contract@example.com", password="pass12345")
        photographer = User.objects.create_user(email="assigned-contract@example.com", password="pass12345")
        unassigned = User.objects.create_user(email="unassigned-contract@example.com", password="pass12345")
        for user in (manager, photographer, unassigned):
            user.account_status = User.AccountStatus.ACTIVE
            user.save()
        StudioMembership.objects.create(
            studio=self.studio, user=manager, role=StudioMembership.Role.MANAGER,
            status=StudioMembership.Status.ACTIVE,
        )
        assigned_membership = StudioMembership.objects.create(
            studio=self.studio, user=photographer, role=StudioMembership.Role.PHOTOGRAPHER,
            status=StudioMembership.Status.ACTIVE,
        )
        StudioMembership.objects.create(
            studio=self.studio, user=unassigned, role=StudioMembership.Role.PHOTOGRAPHER,
            status=StudioMembership.Status.ACTIVE,
        )
        self.booking.assigned_members.add(assigned_membership)
        url = reverse("photographer_workspace:contract_create", args=[self.booking.pk])
        for user in (manager, photographer):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(unassigned)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_anonymous_user_is_redirected_to_login(self):
        url = reverse("photographer_workspace:contract_create", args=[self.booking.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_merge_fields_render_real_values_and_unknown_fields_survive(self):
        self.crm_client.email = "maya@example.com"
        self.crm_client.save(update_fields=["email"])
        self.booking.location = "City Studio"
        self.booking.booking_value = "425.00"
        self.booking.save(update_fields=["location", "booking_value"])
        content = "Hello {{ client.full_name }} at {{ booking.location }} — {{ unknown.value }}"
        rendered = render_merge_fields(content, self.booking)
        self.assertIn("Maya Cole", rendered)
        self.assertIn("City Studio", rendered)
        self.assertIn("{{ unknown.value }}", rendered)

    def test_template_crud_validation_archive_duplicate_and_tenant_isolation(self):
        self.client.force_login(self.owner)
        list_url = reverse("photographer_workspace:contract_templates")
        create_url = reverse("photographer_workspace:contract_template_create")
        self.assertContains(self.client.get(list_url), "Portrait standard")
        invalid = self.client.post(create_url, {
            "name": "Invalid", "title": "Invalid", "category": "general",
            "content": "Hello {{ client.secret }}", "is_active": "on",
        })
        self.assertContains(invalid, "Unsupported merge field")
        created = self.client.post(create_url, {
            "name": "Wedding", "title": "Wedding terms", "category": "wedding",
            "description": "Ceremony agreement", "content": "Hello {{ client.first_name }}",
            "is_active": "on",
        })
        self.assertRedirects(created, list_url)
        item = ContractTemplate.objects.get(name="Wedding")
        edit = self.client.post(reverse("photographer_workspace:contract_template_edit", args=[item.pk]), {
            "name": "Wedding revised", "title": "Wedding terms", "category": "wedding",
            "description": "Updated", "content": "Hello {{ client.full_name }}", "is_active": "on",
        })
        self.assertRedirects(edit, list_url)
        item.refresh_from_db()
        self.assertEqual(item.version, 2)
        self.client.post(reverse("photographer_workspace:contract_template_action", args=[item.pk]), {"action": "duplicate"})
        self.assertTrue(ContractTemplate.objects.filter(photographer=self.studio, name__contains="(copy)").exists())
        self.client.post(reverse("photographer_workspace:contract_template_action", args=[item.pk]), {"action": "toggle_active"})
        item.refresh_from_db()
        self.assertFalse(item.is_active)
        create_page = self.client.get(reverse("photographer_workspace:contract_create", args=[self.booking.pk]))
        self.assertNotContains(create_page, f'<option value="{item.pk}">', html=True)
        other_owner, _studio, _client, _booking, other_template = self.make_studio("template-private@example.com")
        other_template.name = "Private other workspace template"
        other_template.save(update_fields=["name"])
        self.assertNotContains(self.client.get(list_url), other_template.name)
        self.assertEqual(self.client.get(reverse("photographer_workspace:contract_template_edit", args=[other_template.pk])).status_code, 404)

    def test_draft_customization_persists_without_changing_template(self):
        contract = create_contract_from_template(booking=self.booking, template=self.template, actor=self.owner)
        self.client.force_login(self.owner)
        url = reverse("photographer_workspace:contract_customize", args=[contract.pk])
        response = self.client.post(url, {"title": "Personal terms", "content": "Customized persisted terms", "action": "save"})
        self.assertRedirects(response, url)
        contract.refresh_from_db()
        self.template.refresh_from_db()
        self.assertEqual(contract.content, "Customized persisted terms")
        self.assertEqual(self.template.content, "Original persisted terms")
        self.client.logout()
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(url), "Customized persisted terms")

    def test_template_management_requires_settings_permission(self):
        manager = User.objects.create_user(email="template-manager@example.com", password="pass12345")
        manager.account_status = User.AccountStatus.ACTIVE
        manager.save()
        StudioMembership.objects.create(studio=self.studio, user=manager, role=StudioMembership.Role.MANAGER,
                                        status=StudioMembership.Status.ACTIVE)
        self.client.force_login(manager)
        self.assertEqual(self.client.get(reverse("photographer_workspace:contract_templates")).status_code, 403)
