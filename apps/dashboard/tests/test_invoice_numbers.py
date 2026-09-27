from django.test import TransactionTestCase
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.dashboard.invoices import next_invoice_number


class InvoiceNumberTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.user = User.objects.create_user(
            email="invoice-owner@example.com",
            password="TestPass123!",
            first_name="Amara",
            last_name="Reed",
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            last_active_workspace=User.Workspace.PHOTOGRAPHER,
        )
        self.profile = PhotographerProfile.objects.create(
            user=self.user,
            business_name="North & Pine",
            onboarding_completed=True,
        )

    def test_next_invoice_number_can_be_previewed_outside_atomic_transaction(self):
        year = timezone.localdate().year
        self.assertEqual(next_invoice_number(self.profile), f"INV-{year}-0001")
