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

    def test_supported_currencies_and_deposit_types(self):
        from apps.clients.payment_terms import parse_payment_terms
        for currency in ("USD", "CAD", "GBP", "EUR", "AUD", "NZD", "CHF", "GHS", "NGN", "ZAR", "INR", "AED"):
            for kind, raw in (("fixed", "625"), ("percentage", "25")):
                with self.subTest(currency=currency, kind=kind):
                    terms = parse_payment_terms({"price": "2500", "payment_currency": currency,
                        "deposit_required": "on", "deposit_type": kind, "deposit_input": raw,
                        "deposit_due_date": "2026-12-01", "balance_due_date": "2026-12-12"}, "USD")
                    self.assertEqual(terms["deposit_amount"], Decimal("625"))
                    self.assertEqual(terms["payment_currency"], currency)

    def test_invalid_saved_schedule(self):
        from django.core.exceptions import ValidationError
        from apps.clients.payment_terms import validate_saved_payment_terms
        booking = self.booking()
        booking.deposit_due_date = None
        with self.assertRaises(ValidationError):
            validate_saved_payment_terms(booking)

    def test_unsigned_preview_refresh_and_locked_preview(self):
        from unittest.mock import patch
        from apps.clients.contracts import contract_preview_content
        booking = self.booking()
        contract = SimpleNamespace(booking=booking, locked_at=None, rendered_content="",
            content="2. Agreed fee and payment\nService fee: GBP 100.00. The parties will confirm the deposit, payment schedule and applicable taxes in writing before signing.")
        with patch("apps.clients.contracts.merge_context", side_effect=lambda b: {"booking.payment_terms": payment_clause(b)}):
            first = contract_preview_content(contract)
            self.assertIn("GBP 625.00", first)
            self.assertNotIn("GBP 100.00", first)
            booking.deposit_amount = Decimal("500")
            self.assertIn("GBP 500.00", contract_preview_content(contract))
            contract.locked_at = date.today()
            contract.rendered_content = first
            self.assertEqual(contract_preview_content(contract), first)
