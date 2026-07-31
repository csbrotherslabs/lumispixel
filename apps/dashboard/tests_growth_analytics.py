from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientSession, Lead
from apps.dashboard.growth_analytics import (
    growth_summary, growth_window, lead_funnel, lead_source_performance,
)


class GrowthAnalyticsTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.user = User.objects.create_user(email="growth-metrics@example.com", password="test")
        self.profile = PhotographerProfile.objects.create(user=self.user, slug="growth-metrics")
        other_user = User.objects.create_user(email="other-growth@example.com", password="test")
        self.other = PhotographerProfile.objects.create(user=other_user, slug="other-growth")

    def _timestamp(self, instance, days_ago):
        stamp = timezone.make_aware(datetime.combine(self.today - timedelta(days=days_ago), datetime.min.time()))
        type(instance).objects.filter(pk=instance.pk).update(created_at=stamp)
        instance.created_at = stamp
        return instance

    def test_summary_calculates_decimal_metrics_and_scopes_owner(self):
        referral = self._timestamp(Lead.objects.create(
            photographer=self.profile, first_name="Rae", status=Lead.Status.BOOKED, lead_source="Client referral"), 3)
        self._timestamp(Lead.objects.create(photographer=self.profile, first_name="New"), 2)
        self._timestamp(Lead.objects.create(photographer=self.other, first_name="Private", status=Lead.Status.BOOKED), 2)
        client = Client.objects.create(photographer=self.profile, first_name="Rae", converted_lead=referral)
        prior = ClientSession.objects.create(photographer=self.profile, client=client, session_type="Portrait",
                                             starts_at=timezone.now(), status=ClientSession.Status.CONFIRMED,
                                             booking_value=Decimal("100.00"))
        self._timestamp(prior, 40)
        current = ClientSession.objects.create(photographer=self.profile, client=client, session_type="Wedding",
                                               starts_at=timezone.now(), status=ClientSession.Status.CONFIRMED,
                                               booking_value=Decimal("250.25"))
        self._timestamp(current, 1)

        result = growth_summary(self.profile, "last_30_days", today=self.today)

        self.assertEqual(result["values"]["new_leads"], 2)
        self.assertEqual(result["values"]["confirmed_bookings"], 1)
        self.assertEqual(result["values"]["conversion_rate"], Decimal("50.0"))
        self.assertEqual(result["values"]["average_booking_value"], Decimal("250.25"))
        self.assertEqual(result["values"]["repeat_client_rate"], Decimal("100.0"))
        self.assertEqual(result["values"]["referral_bookings"], 1)

    def test_empty_denominators_and_equivalent_period(self):
        result = growth_summary(self.profile, "last_90_days", today=self.today)
        self.assertIsNone(result["values"]["conversion_rate"])
        self.assertIsNone(result["values"]["average_booking_value"])
        self.assertEqual(result["cards"][2]["formatted_value"], "—")
        window = growth_window("last_90_days", self.today)
        self.assertEqual((window.end - window.start).days, (window.previous_end - window.previous_start).days)

    def test_funnel_and_sources_use_owner_scoped_records(self):
        website = self._timestamp(Lead.objects.create(
            photographer=self.profile, first_name="Web", status=Lead.Status.BOOKED,
            lead_source="website", estimated_value=Decimal("900.00")), 2)
        self._timestamp(Lead.objects.create(
            photographer=self.profile, first_name="Mystery", status=Lead.Status.CONTACTED,
            lead_source="Unmapped campaign"), 1)
        self._timestamp(Lead.objects.create(
            photographer=self.other, first_name="Private", status=Lead.Status.BOOKED,
            lead_source="website"), 1)
        client = Client.objects.create(photographer=self.profile, first_name="Web", converted_lead=website)
        booking = ClientSession.objects.create(
            photographer=self.profile, client=client, session_type="Portrait", starts_at=timezone.now(),
            status=ClientSession.Status.CONFIRMED, booking_value=Decimal("600.00"))
        self._timestamp(booking, 1)

        funnel = lead_funnel(self.profile, "last_30_days", today=self.today)
        sources = lead_source_performance(self.profile, "last_30_days", sort_key="value", today=self.today)

        self.assertEqual([stage["label"] for stage in funnel], [
            "New lead", "Contacted", "Consultation scheduled", "Proposal or quote sent",
            "Booking pending", "Confirmed booking",
        ])
        self.assertEqual(funnel[-1]["count"], 1)
        self.assertIn("status=confirmed", funnel[-1]["url"])
        self.assertEqual(sources[0]["source"], "Website")
        self.assertEqual(sources[0]["bookings"], 1)
        self.assertEqual(sources[0]["conversion_rate"], Decimal("100.0"))
        self.assertEqual(sources[1]["source"], "Other")
