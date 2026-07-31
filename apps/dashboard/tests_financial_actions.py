from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientInvoice, InvoiceCredit, InvoicePayment, PaymentRefund
from apps.dashboard.financial_actions import add_credit, issue_refund, record_payment, use_credit


class FinancialActionTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="finance-actions@example.com", password="test", email_verified=True,
                                        account_status=User.AccountStatus.ACTIVE, primary_role=User.PrimaryRole.PHOTOGRAPHER)
        self.profile = PhotographerProfile.objects.create(user=user, slug="finance-actions", onboarding_completed=True)
        self.client_record = Client.objects.create(photographer=self.profile, first_name="Alex")
        self.invoice = ClientInvoice.objects.create(photographer=self.profile, client=self.client_record,
            invoice_number="INV-ACTION", total=Decimal("500.00"), status=ClientInvoice.Status.SENT)

    def test_partial_payment_is_decimal_atomic_and_idempotent(self):
        data = {"client": self.client_record.pk, "invoice": self.invoice.pk, "amount": "125.25",
                "processor_fee": "3.10", "method": "card", "submission_key": "payment-once"}
        payment, duplicate = record_payment(self.profile, data)
        second, second_duplicate = record_payment(self.profile, data)
        self.invoice.refresh_from_db()
        self.assertFalse(duplicate)
        self.assertTrue(second_duplicate)
        self.assertEqual(payment.pk, second.pk)
        self.assertEqual(self.invoice.amount_paid, Decimal("125.25"))
        self.assertEqual(self.invoice.status, ClientInvoice.Status.PARTIALLY_PAID)

    def test_refunds_enforce_remaining_value_and_restore_invoice_balance(self):
        payment, _ = record_payment(self.profile, {"client": self.client_record.pk, "invoice": self.invoice.pk,
            "amount": "200", "method": "cash", "submission_key": "cash-payment"})
        refund, _ = issue_refund(self.profile, {"payment": payment.pk, "amount": "75.50", "reason": "Scope changed",
                                                       "submission_key": "refund-once"})
        self.invoice.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(refund.amount, Decimal("75.50"))
        self.assertEqual(self.invoice.amount_paid, Decimal("124.50"))
        self.assertEqual(payment.status, InvoicePayment.Status.COMPLETED)
        with self.assertRaises(ValidationError):
            issue_refund(self.profile, {"payment": payment.pk, "amount": "125", "reason": "Too much"})

    def test_credit_tracks_original_remaining_and_cannot_be_overused(self):
        credit, _ = add_credit(self.profile, {"client": self.client_record.pk, "invoice": self.invoice.pk,
            "amount": "80", "reason": "Service recovery", "expires_at": date(2027, 1, 1), "submission_key": "credit-once"})
        use_credit(self.profile, credit.pk, "25.25")
        credit.refresh_from_db()
        self.assertEqual(credit.original_amount, Decimal("80.00"))
        self.assertEqual(credit.remaining_amount, Decimal("54.75"))
        with self.assertRaises(ValidationError):
            use_credit(self.profile, credit.pk, "54.76")

    def test_action_endpoint_requires_confirmation_and_owner_scopes_invoice(self):
        self.client.force_login(self.profile.user)
        url = reverse("photographer_workspace:financial_action", args=["payment"])
        denied = self.client.post(url, {"confirmed": "no"})
        self.assertEqual(denied.status_code, 400)
        response = self.client.post(url, {"confirmed": "yes", "client": self.client_record.pk,
            "invoice": self.invoice.pk, "amount": "20", "method": "check", "submission_key": "endpoint-payment"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(InvoicePayment.objects.count(), 1)
