from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientInvoice, InvoicePayment


class FinancialSchemaIntegrityTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="schema-integrity@example.com", password="testpass")
        self.owner = PhotographerProfile.objects.create(user=user, slug="schema-integrity")
        self.client_record = Client.objects.create(photographer=self.owner, first_name="Client")
        self.invoice = ClientInvoice.objects.create(
            photographer=self.owner, client=self.client_record, invoice_number="SCHEMA-1",
            subtotal=Decimal("100.00"), total=Decimal("100.00"),
        )

    def test_database_rejects_negative_invoice_total(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ClientInvoice.objects.create(
                    photographer=self.owner, client=self.client_record, invoice_number="SCHEMA-2",
                    subtotal=Decimal("10.00"), total=Decimal("-1.00"),
                )

    def test_database_rejects_invoice_overpayment(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ClientInvoice.objects.create(
                    photographer=self.owner, client=self.client_record, invoice_number="SCHEMA-3",
                    subtotal=Decimal("10.00"), total=Decimal("10.00"), amount_paid=Decimal("10.01"),
                )

    def test_database_rejects_zero_or_negative_payment(self):
        for amount in (Decimal("0.00"), Decimal("-1.00")):
            with self.subTest(amount=amount):
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        InvoicePayment.objects.create(
                            photographer=self.owner, invoice=self.invoice, amount=amount,
                        )
