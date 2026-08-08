from datetime import date
from decimal import Decimal

from datetime import datetime

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientInvoice, ClientSession, InvoiceCredit, InvoicePayment, PaymentRefund
from apps.dashboard.financial import ZERO, date_window, financial_summary, format_currency
from apps.dashboard.financial_analytics import _grouping, _labels


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

    def test_chart_labels_do_not_use_platform_specific_strftime_flags(self):
        self.assertEqual(_labels(date(2026, 7, 1), 2, "daily"), ["Jul 1", "Jul 2"])
        self.assertEqual(_labels(date(2026, 1, 1), 2, "monthly"), ["Jan 2026", "Feb 2026"])


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

    def test_kpi_change_semantics_are_not_inferred_from_direction_alone(self):
        profile = self.profile("semantic-kpis")
        self.invoice(profile, suffix="previous", total=Decimal("100.00"), created=date(2026, 6, 1),
                     status=ClientInvoice.Status.SENT, due_date=date(2026, 6, 15))
        self.invoice(profile, suffix="current", total=Decimal("500.00"),
                     status=ClientInvoice.Status.SENT, due_date=date(2026, 7, 1))

        cards = {card["title"]: card for card in financial_summary(
            profile, "this_month", today=self.today
        )["cards"]}

        self.assertEqual(cards["Outstanding"]["change_variant"], "neutral")
        self.assertEqual(cards["Overdue"]["change_variant"], "danger")
        self.assertEqual(cards["Overdue"]["display_trend"], "increase")

    def test_transactions_page_uses_real_view_summary_and_active_navigation(self):
        profile = self.profile("transactions")
        self.client.force_login(profile.user)

        response = self.client.get(reverse("photographer_workspace:transactions"), {"range": "this_year"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "photographer_workspace/financial/transactions.html")
        self.assertEqual(response.context["range_key"], "this_year")
        self.assertEqual(len(response.context["transaction_summary"]), 4)
        financial_group = next(group for group in response.context["workspace_nav"] if group["title"] == "Financial")
        self.assertEqual([item["title"] for item in financial_group["items"]], ["Overview", "Transactions"])
        self.assertTrue(next(item for item in financial_group["items"] if item["title"] == "Transactions")["active"])

    def test_transactions_filters_are_bookmarkable_and_preserved_across_views(self):
        profile = self.profile("filtered-transactions")
        self.client.force_login(profile.user)

        response = self.client.get(reverse("photographer_workspace:transactions"), {
            "view": "payments", "q": "INV-42", "status": "completed", "amount_min": "100",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["transaction_view"], "payments")
        self.assertEqual(response.context["active_filter_count"], 3)
        self.assertContains(response, "All activity")
        self.assertContains(response, "Invoices")
        self.assertContains(response, "Refunds")
        invoices_view = next(item for item in response.context["transaction_views"] if item["value"] == "invoices")
        self.assertIn("q=INV-42", invoices_view["url"])
        self.assertIn("status=completed", invoices_view["url"])
        self.assertContains(response, "Search: INV-42")
        self.assertContains(response, "Minimum: 100")

    def test_unified_transactions_are_decimal_backed_sorted_and_paginated(self):
        profile = self.profile("unified-transactions")
        invoice = self.invoice(profile, status=ClientInvoice.Status.PARTIALLY_PAID, total=Decimal("125.50"))
        payment = InvoicePayment.objects.create(photographer=profile, invoice=invoice, amount=Decimal("75.25"))
        PaymentRefund.objects.create(photographer=profile, payment=payment, amount=Decimal("10.10"))
        InvoiceCredit.objects.create(photographer=profile, invoice=invoice, amount=Decimal("5.15"))
        self.client.force_login(profile.user)

        response = self.client.get(reverse("photographer_workspace:transactions"), {
            "range": "all_time", "sort": "amount", "direction": "desc", "page_size": "10",
        })

        records = response.context["transaction_records"]
        self.assertEqual(records["total"], 4)
        self.assertTrue(all(isinstance(row["sort_amount"], Decimal) for row in records["rows"]))
        self.assertEqual([row["type"] for row in records["rows"]], ["invoice", "payment", "credit", "refund"])
        refund = next(row for row in records["rows"] if row["type"] == "refund")
        self.assertEqual(refund["gross"], "-$10.10")
        self.assertEqual(refund["amount_label"], "Cash refunded")
        self.assertEqual(refund["amount_meaning"], "Cash out of the business")
        invoice_row = next(row for row in records["rows"] if row["type"] == "invoice")
        self.assertEqual(invoice_row["amount_meaning"], "Outstanding; not received revenue")
        self.assertContains(response, "Transaction records")
        self.assertContains(response, "Rows per page")
        self.assertContains(response, "data-row-url")

    def test_unified_transactions_support_record_filter_and_filtered_empty_state(self):
        profile = self.profile("transaction-filtering")
        self.invoice(profile, status=ClientInvoice.Status.SENT)
        self.client.force_login(profile.user)

        payments = self.client.get(reverse("photographer_workspace:transactions"), {
            "range": "all_time", "record_type": "payment",
        })

        self.assertEqual(payments.context["transaction_records"]["total"], 0)
        self.assertEqual(payments.context["transaction_state"], "empty")
        self.assertContains(payments, "No matching transactions")

    def test_record_detail_drawer_returns_reusable_owner_scoped_markup(self):
        profile = self.profile("drawer-owner")
        invoice = self.invoice(profile, status=ClientInvoice.Status.PARTIALLY_PAID,
                               total=Decimal("325.00"), amount_paid=Decimal("100.00"))
        payment = InvoicePayment.objects.create(photographer=profile, invoice=invoice, amount=Decimal("100.00"),
                                                method=InvoicePayment.Method.CARD, processor_fee=Decimal("3.25"),
                                                internal_note="Reconciled against the card settlement.")
        self.client.force_login(profile.user)

        response = self.client.get(reverse("photographer_workspace:financial_record_detail", args=["payment", payment.pk]))

        self.assertEqual(response.status_code, 200)
        markup = response.json()["html"]
        for heading in ("Financial summary", "Client and booking", "Record details", "Related records",
                        "Activity history", "Internal notes"):
            self.assertIn(heading, markup)
        self.assertIn(f"PAY-{payment.pk:06d}", markup)
        self.assertIn("$100.00", markup)
        self.assertIn("$3.25", markup)
        self.assertIn("$96.75", markup)
        self.assertIn("Card", markup)
        self.assertIn("Reconciled against the card settlement.", markup)
        self.assertIn("Issue refund", markup)

    def test_record_detail_does_not_disclose_another_studios_record(self):
        owner, intruder = self.profile("drawer-private"), self.profile("drawer-intruder")
        private_invoice = self.invoice(owner, suffix="private-client")
        self.client.force_login(intruder.user)

        response = self.client.get(reverse("photographer_workspace:financial_record_detail", args=["invoice", private_invoice.pk]))

        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "private-client", status_code=404)

    def test_transactions_include_direct_link_and_drawer_accessibility_shell(self):
        profile = self.profile("drawer-shell")
        invoice = self.invoice(profile, status=ClientInvoice.Status.SENT)
        self.client.force_login(profile.user)

        response = self.client.get(reverse("photographer_workspace:transactions"), {"range": "all_time", "invoice": invoice.pk})

        self.assertContains(response, f"?invoice={invoice.pk}")
        self.assertContains(response, 'role="dialog"')
        self.assertContains(response, 'aria-modal="true"')
        self.assertContains(response, "financial_record_drawer.js")
