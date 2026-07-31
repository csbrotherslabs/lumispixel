from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientActivity, ClientSession, Lead
from apps.dashboard.growth_analytics import (
    booking_value_by_source, growth_opportunities, growth_summary, growth_window, lead_funnel,
    lead_source_performance, recent_growth_activity, reputation_summary, service_performance,
)
from apps.dashboard.models import Review


class GrowthAnalyticsTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.user = User.objects.create_user(email="growth-metrics@example.com", password="test")
        self.profile = PhotographerProfile.objects.create(user=self.user, slug="growth-metrics")
        other_user = User.objects.create_user(email="other-growth@example.com", password="test")
        self.other = PhotographerProfile.objects.create(user=other_user, slug="other-growth")

    def _timestamp(self, instance, days_ago):
        stamp = timezone.make_aware(datetime.combine(self.today - timedelta(days=days_ago), datetime.min.time()))
        updates = {"created_at": stamp}
        if isinstance(instance, ClientSession) and instance.status in (ClientSession.Status.CONFIRMED, ClientSession.Status.COMPLETED):
            updates["confirmed_at"] = stamp
            instance.confirmed_at = stamp
        type(instance).objects.filter(pk=instance.pk).update(**updates)
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

        chart = booking_value_by_source(self.profile, "last_30_days", today=self.today)
        self.assertEqual(chart["rows"][0]["source"], "Website")
        self.assertEqual(chart["rows"][0]["value"], Decimal("600.00"))
        self.assertEqual(chart["rows"][0]["percent"], Decimal("100.0"))

        services = service_performance(self.profile, "last_30_days", today=self.today)
        portrait = next(row for row in services if row["service"] == "Portrait")
        self.assertEqual(portrait["bookings"], 1)
        self.assertEqual(portrait["formatted_value"], "$600.00")
        self.assertIn("Highest value", portrait["badges"])

    def test_opportunities_are_data_based_ranked_and_owner_scoped(self):
        old = timezone.now() - timedelta(days=5)
        lead = Lead.objects.create(photographer=self.profile, first_name="Follow", status=Lead.Status.NEW)
        Lead.objects.filter(pk=lead.pk).update(created_at=old)
        private = Lead.objects.create(photographer=self.other, first_name="Private", status=Lead.Status.NEW)
        Lead.objects.filter(pk=private.pk).update(created_at=old)

        result = growth_opportunities(self.profile, today=self.today)

        self.assertEqual(result["items"][0]["title"], "Leads need a follow-up")
        self.assertEqual(result["items"][0]["priority"], "High")
        self.assertEqual(result["items"][0]["count"], 1)
        self.assertEqual(growth_opportunities(self.profile, today=self.today)["total"], 1)

    def test_recent_activity_exposes_only_supported_owner_events(self):
        lead = Lead.objects.create(photographer=self.profile, first_name="Ada", lead_source="Website")
        ClientActivity.objects.create(photographer=self.profile, lead=lead,
                                      event_type=ClientActivity.EventType.LEAD_CREATED,
                                      metadata={"team_member": "Sam"})
        other_lead = Lead.objects.create(photographer=self.other, first_name="Private")
        ClientActivity.objects.create(photographer=self.other, lead=other_lead,
                                      event_type=ClientActivity.EventType.LEAD_CREATED)

        rows = recent_growth_activity(self.profile)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["activity"], "New lead received")
        self.assertEqual(rows[0]["person"], "Ada")
        self.assertEqual(rows[0]["source"], "Website")
        self.assertEqual(rows[0]["team_member"], "Sam")

    def test_booking_uses_confirmation_date_not_creation_or_session_date(self):
        client = Client.objects.create(photographer=self.profile, first_name="Later")
        booking = ClientSession.objects.create(
            photographer=self.profile, client=client, session_type="Portrait",
            starts_at=timezone.now() + timedelta(days=180), status=ClientSession.Status.CONFIRMED,
            booking_value=Decimal("125.00"),
        )
        old = timezone.now() - timedelta(days=60)
        ClientSession.objects.filter(pk=booking.pk).update(created_at=old)

        self.assertEqual(growth_summary(self.profile, "last_30_days", today=self.today)["values"]["confirmed_bookings"], 1)

    def test_previous_period_comparison_uses_equal_non_overlapping_windows(self):
        current = self._timestamp(Lead.objects.create(photographer=self.profile, first_name="Current"), 2)
        self._timestamp(Lead.objects.create(photographer=self.profile, first_name="Previous"), 32)

        card = growth_summary(self.profile, "last_30_days", today=self.today)["cards"][0]

        self.assertEqual(current.first_name, "Current")
        self.assertEqual(card["percentage"], Decimal("0.0"))
        self.assertEqual(card["trend"], "neutral")

    def test_missing_source_is_unknown_without_mutating_lead(self):
        lead = self._timestamp(Lead.objects.create(photographer=self.profile, first_name="No source", lead_source=""), 1)

        row = lead_source_performance(self.profile, "last_30_days", today=self.today)[0]

        self.assertEqual(row["source"], "Unknown")
        self.assertIn("source=__unknown__", row["url"])
        lead.refresh_from_db()
        self.assertEqual(lead.lead_source, "")

    def test_cancelled_booking_has_no_booking_value_and_is_reported_for_service(self):
        client = Client.objects.create(photographer=self.profile, first_name="Cancelled")
        booking = ClientSession.objects.create(
            photographer=self.profile, client=client, session_type="Wedding", starts_at=timezone.now(),
            status=ClientSession.Status.CANCELLED, booking_value=Decimal("900.00"),
        )
        self._timestamp(booking, 1)

        summary = growth_summary(self.profile, "last_30_days", today=self.today)
        service = service_performance(self.profile, "last_30_days", today=self.today)[0]

        self.assertEqual(summary["values"]["confirmed_bookings"], 0)
        self.assertEqual(service["booking_value"], Decimal("0.00"))
        self.assertEqual(service["cancelled"], 1)

    def test_review_metrics_use_review_date_and_owner_scope(self):
        now = timezone.now()
        Review.objects.create(photographer=self.profile, reviewer_name="Recent", rating=5, reviewed_at=now)
        Review.objects.create(photographer=self.profile, reviewer_name="Old", rating=1,
                              reviewed_at=now - timedelta(days=60))
        Review.objects.create(photographer=self.other, reviewer_name="Private", rating=1, reviewed_at=now)

        report = reputation_summary(self.profile, "last_30_days", today=self.today)

        self.assertEqual(dict(report["metrics"])["Average rating"], "5.0 / 5")
        self.assertEqual(dict(report["metrics"])["Total reviews"], 1)

    def test_growth_export_requires_photographer_permission(self):
        response = self.client.get(reverse("photographer_workspace:growth_export"))
        self.assertEqual(response.status_code, 302)
