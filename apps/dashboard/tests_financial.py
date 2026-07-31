from datetime import date
from decimal import Decimal

from datetime import datetime

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientInvoice, ClientSession, InvoiceCredit, InvoicePayment, PaymentRefund
from apps.dashboard.financial import ZERO, date_window, financial_summary, format_currency
from apps.dashboard.financial_analytics import _grouping


class FinancialSelectorTests(SimpleTestCase):
    def test_currency_formatter_uses_decimal_values_and_handles_empty(self):
        self.assertEqual(format_currency(Decimal("1234.505"), "USD"), "$1,234.51")
        self.assertEqual(format_currency(Decimal("-12.10"), "EUR"), "-€12.10")
        self.assertEqual(format_currency(None, "USD"), "—")

    def test_month_window_includes_matching_previous_period(self):
        window = date_window("this_month", date(2026, 7, 31))
        self.assertEqual((window.start, window.end), (date(2026, 7, 1), date(2026, 7, 31)))
        self.assertEqual((window.previous_start, window.previous_end), (date(2026, 6, 1), date(2026, 6, 30)))

    def test_all_time_has_no_artificial_comparison_window(self):
        window = date_window("all_time", date(2026, 7, 31))
        self.assertIsNone(window.start)
        self.assertIsNone(window.previous_end)

    def test_chart_grouping_adapts_to_selected_range_length(self):
        self.assertEqual(_grouping(date(2026, 7, 1), date(2026, 7, 31))[0], "daily")
        self.assertEqual(_grouping(date(2026, 1, 1), date(2026, 4, 30))[0], "weekly")
        self.assertEqual(_grouping(date(2025, 1, 1), date(2026, 7, 31))[0], "monthly")


class FinancialDatabaseSelectorTests(TestCase):
    today = date(2026, 7, 31)

    def profile(self, suffix):
        user = User.objects.create_user(email=f"{suffix}@example.com", password="test", email_verified=True,
                                        account_status=User.AccountStatus.ACTIVE, primary_role=User.PrimaryRole.PHOTOGRAPHER)
        return PhotographerProfile.objects.create(user=user, slug=suffix, onboarding_completed=True)

    def invoice(self, profile, suffix="one", **values):
        client = Client.objects.create(photographer=profile, first_name=suffix)
        created = values.pop("created", self.today)
        invoice = ClientInvoice.objects.create(photographer=profile, client=client, total=values.pop("total", Decimal("500.00")), **values)
        ClientInvoice.objects.filter(pk=invoice.pk).update(created_at=timezone.make_aware(datetime.combine(created, datetime.min.time())))
        return invoice

    def test_cash_refunds_credits_partial_balance_and_booking_value_are_distinct(self):
        profile = self.profile("finance")
        invoice = self.invoice(profile, status=ClientInvoice.Status.PARTIALLY_PAID, due_date=date(2026, 7, 1))
        payment = InvoicePayment.objects.create(photographer=profile, invoice=invoice, amount=Decimal("200.00"),
                                                paid_at=timezone.make_aware(datetime(2026, 7, 10)))
        PaymentRefund.objects.create(photographer=profile, payment=payment, amount=Decimal("25.00"),
                                     refunded_at=timezone.make_aware(datetime(2026, 7, 12)))
        InvoiceCredit.objects.create(photographer=profile, invoice=invoice, amount=Decimal("50.00"),
                                     applied_at=timezone.make_aware(datetime(2026, 7, 15)))
        ClientSession.objects.create(photographer=profile, client=invoice.client, session_type="Wedding",
                                     starts_at=timezone.make_aware(datetime(2026, 7, 20)), status=ClientSession.Status.CONFIRMED,
                                     booking_value=Decimal("900.00"))

        values = financial_summary(profile, "this_month", today=self.today)["values"]
        self.assertEqual(values["collected"], Decimal("200.00"))
        self.assertEqual(values["refunds"], Decimal("25.00"))
        self.assertEqual(values["net_revenue"], Decimal("175.00"))
        self.assertEqual(values["credits"], Decimal("50.00"))
        self.assertEqual(values["outstanding"], Decimal("250.00"))
        self.assertEqual(values["overdue"], Decimal("250.00"))
        self.assertEqual(values["booking_value"], Decimal("900.00"))

    def test_status_date_and_studio_isolation_exclude_invalid_records(self):
        profile, other = self.profile("owner"), self.profile("other")
        invoice = self.invoice(profile, status=ClientInvoice.Status.SENT)
        other_invoice = self.invoice(other, suffix="private", total=Decimal("999.00"), status=ClientInvoice.Status.SENT)
        InvoicePayment.objects.create(photographer=profile, invoice=invoice, amount=Decimal("80.00"), status=InvoicePayment.Status.FAILED)
        InvoicePayment.objects.create(photographer=other, invoice=other_invoice, amount=Decimal("999.00"))
        self.invoice(profile, suffix="draft", total=Decimal("700.00"), status=ClientInvoice.Status.DRAFT)
        self.invoice(profile, suffix="old", total=Decimal("600.00"), status=ClientInvoice.Status.SENT, created=date(2026, 6, 1))

        values = financial_summary(profile, "this_month", today=self.today)["values"]
        self.assertEqual(values["invoice_value"], Decimal("500.00"))
        self.assertEqual(values["collected"], ZERO)

    def test_empty_dataset_returns_decimal_zeroes(self):
        values = financial_summary(self.profile("empty"), "this_month", today=self.today)["values"]
        for key in ("invoice_value", "collected", "refunds", "credits", "net_revenue", "outstanding", "overdue", "booking_value"):
            self.assertEqual(values[key], ZERO)
