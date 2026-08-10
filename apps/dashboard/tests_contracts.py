from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.contracts import create_contract_from_template
from apps.clients.models import Client, ClientSession, Contract, ContractEvent, ContractTemplate
from apps.dashboard.models import StudioMembership


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
