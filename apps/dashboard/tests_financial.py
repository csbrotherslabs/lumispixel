from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from apps.dashboard.financial import date_window, format_currency
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
