from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientSession, Contract, ContractTemplate


class ClientContractsTabTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="contracts-tab@example.com",
            password="testpass",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.photographer = PhotographerProfile.objects.create(
            user=self.user,
            slug="contracts-tab-studio",
            onboarding_completed=True,
        )
        self.client_record = Client.objects.create(
            photographer=self.photographer,
            first_name="Jordan",
            last_name="Lee",
            email="jordan@example.com",
        )
        self.booking = ClientSession.objects.create(
            photographer=self.photographer,
            client=self.client_record,
            event_kind=ClientSession.EventKind.BOOKING,
            session_type="Wedding",
            starts_at=timezone.now() + timedelta(days=30),
            booking_value="3200.00",
            status=ClientSession.Status.CONFIRMED,
        )
        self.template = ContractTemplate.objects.create(
            photographer=self.photographer,
            name="Wedding Agreement",
            title="Wedding Photography Agreement",
            content="Agreement terms",
            created_by=self.user,
        )
        self.contract = Contract.objects.create(
            photographer=self.photographer,
            booking=self.booking,
            client=self.client_record,
            template=self.template,
            title="Jordan & Lee Wedding Agreement",
            content="Agreement terms",
            status=Contract.Status.SENT,
            sent_at=timezone.now(),
            created_by=self.user,
        )
        self.client.force_login(self.user)

    def test_client_detail_exposes_contracts_as_first_class_tab(self):
        response = self.client.get(
            reverse("photographer_workspace:client_detail", args=[self.client_record.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("client_contracts", args=[self.client_record.pk]))
        self.assertContains(response, "Contracts")

    def test_contracts_tab_lists_existing_contract_relationship(self):
        response = self.client.get(reverse("client_contracts", args=[self.client_record.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "photographer_workspace/client_contracts.html")
        self.assertContains(response, self.contract.title)
        self.assertContains(response, "Wedding Agreement")
        self.assertContains(response, "3200.00")
        self.assertContains(
            response,
            reverse("photographer_workspace:contract_detail", args=[self.contract.pk]),
        )
        self.assertContains(response, "Sent")

    def test_contracts_tab_has_empty_state(self):
        other_client = Client.objects.create(
            photographer=self.photographer,
            first_name="No",
            last_name="Contracts",
            email="none@example.com",
        )
        response = self.client.get(reverse("client_contracts", args=[other_client.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No contracts for this client.")

    def test_contracts_tab_does_not_expose_another_workspace_client(self):
        other_user = User.objects.create_user(
            email="other-contracts-tab@example.com",
            password="testpass",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        other_photographer = PhotographerProfile.objects.create(
            user=other_user,
            slug="other-contracts-tab-studio",
            onboarding_completed=True,
        )
        other_client = Client.objects.create(
            photographer=other_photographer,
            first_name="Other",
            last_name="Client",
        )

        response = self.client.get(reverse("client_contracts", args=[other_client.pk]))
        self.assertEqual(response.status_code, 404)
