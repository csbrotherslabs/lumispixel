from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from django.test import SimpleTestCase
from apps.clients.payment_terms import payment_clause

class PaymentClauseTests(SimpleTestCase):
    def booking(self, total="2500", deposit="625", confirmed=True):
        return SimpleNamespace(pricing_confirmed=confirmed, payment_currency="GBP",
            booking_value=Decimal(total), deposit_amount=Decimal(deposit),
            deposit_due_date=date(2026, 12, 1), balance_due_date=date(2026, 12, 12))

    def test_partial_deposit(self):
        clause = payment_clause(self.booking())
        for value in ("GBP 2,500.00", "GBP 625.00", "GBP 1,875.00", "December 01, 2026", "December 12, 2026"):
            self.assertIn(value, clause)

    def test_no_deposit(self):
        self.assertIn("full fee is payable", payment_clause(self.booking(deposit="0")))

    def test_full_advance(self):
        self.assertIn("No further service fee balance", payment_clause(self.booking(deposit="2500")))

    def test_complimentary(self):
        self.assertIn("complimentary", payment_clause(self.booking(total="0", deposit="0")))

    def test_unconfirmed(self):
        self.assertIn("not ready for signature", payment_clause(self.booking(confirmed=False)))
