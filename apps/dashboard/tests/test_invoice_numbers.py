from django.test import TransactionTestCase
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.billing.models import Plan
from apps.dashboard.invoices import next_invoice_number


class InvoiceNumberTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        # TransactionTestCase flushes the test database between tests.
        # Ensure the active free plan exists before the profile post_save
        # signal provisions its default subscription.
        Plan.objects.get_or_create(
            code="free",
            defaults={"name": "Free", "is_active": True},
        )
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
