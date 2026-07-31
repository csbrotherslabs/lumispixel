import csv
import io
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientInvoice, InvoicePayment
from apps.dashboard.financial_bulk import available_actions, selected_objects


class FinancialBulkTests(TestCase):
    def profile(self, slug):
        user = User.objects.create_user(email=f"{slug}@example.com", password="test", email_verified=True,
                                        account_status=User.AccountStatus.ACTIVE,
                                        primary_role=User.PrimaryRole.PHOTOGRAPHER)
        return PhotographerProfile.objects.create(user=user, slug=slug, onboarding_completed=True)

    def setUp(self):
        self.owner, self.other = self.profile("bulk-owner"), self.profile("bulk-other")
        self.client_record = Client.objects.create(photographer=self.owner, first_name="Ari", email="ari@example.com")
        self.invoice = ClientInvoice.objects.create(photographer=self.owner, client=self.client_record,
            invoice_number="INV-BULK", total=Decimal("125.00"), status=ClientInvoice.Status.DRAFT)
        other_client = Client.objects.create(photographer=self.other, first_name="Private")
        self.private = ClientInvoice.objects.create(photographer=self.other, client=other_client,
            invoice_number="INV-PRIVATE", total=Decimal("999.00"), status=ClientInvoice.Status.DRAFT)
        self.client.force_login(self.owner.user)

    def test_capabilities_prevent_unsafe_mixed_record_actions(self):
        payment = InvoicePayment.objects.create(photographer=self.owner, invoice=self.invoice, amount=Decimal("10"))
        rows = selected_objects(self.owner, [f"invoice-{self.invoice.pk}", f"payment-{payment.pk}"])
        self.assertEqual(available_actions(rows), ["export", "note"])
        response = self.client.post(reverse("photographer_workspace:financial_transaction_bulk"), {
            "action": "void", "records": [f"invoice-{self.invoice.pk}", f"payment-{payment.pk}"],
        })
        self.assertEqual(response.status_code, 400)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, ClientInvoice.Status.DRAFT)

    def test_bulk_operations_are_studio_scoped_and_atomic(self):
        response = self.client.post(reverse("photographer_workspace:financial_transaction_bulk"), {
            "action": "void", "records": [f"invoice-{self.invoice.pk}", f"invoice-{self.private.pk}"],
        })
        self.assertEqual(response.status_code, 400)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, ClientInvoice.Status.DRAFT)

    def test_filtered_and_selected_csv_use_approved_columns(self):
        url = reverse("photographer_workspace:financial_transaction_export")
        response = self.client.get(url, {"range": "all_time", "columns": ["reference", "client_email", "bogus"]})
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(rows[0], ["Reference", "Client email"])
        self.assertEqual(rows[1], [f"INV-{self.invoice.pk:06d}", "ari@example.com"])
        self.assertNotContains(response, "INV-PRIVATE")

    def test_eligible_drafts_can_be_voided(self):
        response = self.client.post(reverse("photographer_workspace:financial_transaction_bulk"), {
            "action": "void", "records": [f"invoice-{self.invoice.pk}"],
        })
        self.assertEqual(response.status_code, 200)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, ClientInvoice.Status.VOID)
