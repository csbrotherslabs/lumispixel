from datetime import datetime, time, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientInvoice, ClientSession, InvoicePayment
from apps.dashboard.models import Review, StudioMembership
from apps.dashboard.team_performance import calculate_period_metrics, team_performance_report
from apps.galleries.models import Gallery


class TeamPerformanceMetricTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="owner@metrics.example", password="test-pass",
                                             primary_role=User.PrimaryRole.PHOTOGRAPHER)
        self.studio = PhotographerProfile.objects.create(user=self.user, slug="metric-studio",
                                                          onboarding_completed=True)
        self.member = StudioMembership.objects.create(
            studio=self.studio, user=self.user, role=StudioMembership.Role.OWNER,
            status=StudioMembership.Status.ACTIVE, working_days=[str(i) for i in range(1, 8)],
            working_hours_start=time(9), working_hours_end=time(17),
        )
        self.client_record = Client.objects.create(photographer=self.studio, first_name="Client")

    def test_summary_uses_completed_assignments_actual_delivery_and_collected_payment(self):
        today = timezone.localdate()
        starts_at = timezone.make_aware(datetime.combine(today - timedelta(days=2), time(10)))
        booking = ClientSession.objects.create(
            photographer=self.studio, client=self.client_record, session_type="Portrait",
            starts_at=starts_at, duration_minutes=120, status=ClientSession.Status.COMPLETED,
            booking_value=Decimal("999.00"),
        )
        booking.assigned_members.add(self.member)
        invoice = ClientInvoice.objects.create(photographer=self.studio, client=self.client_record,
                                               booking=booking, total=Decimal("300.00"))
        InvoicePayment.objects.create(photographer=self.studio, invoice=invoice,
                                      amount=Decimal("250.00"), status=InvoicePayment.Status.COMPLETED)
        gallery = Gallery.objects.create(
            photographer=self.studio, client=self.client_record, name="Delivered", slug="delivered",
            event_date=today - timedelta(days=2), status=Gallery.Status.DELIVERED,
            published_at=timezone.make_aware(datetime.combine(today, time(10))),
        )
        gallery.assigned_members.add(self.member)
        for rating in (4, 5, 5):
            Review.objects.create(photographer=self.studio, reviewer_name="Verified", rating=rating,
                                  reviewed_at=timezone.now())

        metrics = calculate_period_metrics(self.studio, [self.member], today - timedelta(days=6), today)

        self.assertEqual(metrics["shoots"], 1)
        self.assertEqual(metrics["completion_rate"], 100)
        self.assertEqual(metrics["galleries"], 1)
        self.assertEqual(metrics["gallery_delivery"], 2 + 10 / 24)
        self.assertIsNone(metrics["editing_turnaround"])
        self.assertEqual(metrics["revenue"], Decimal("250.00"))
        self.assertAlmostEqual(metrics["satisfaction"], 14 / 3)
        self.assertGreater(metrics["capacity"], 0)

    def test_report_exposes_comparisons_definitions_and_honest_missing_data(self):
        report = team_performance_report(self.studio, {"range": "30d", "compare": "year"})
        metrics = {metric["key"]: metric for metric in report["summary_metrics"]}

        self.assertEqual(set(metrics), {"shoots", "completion_rate", "galleries", "editing_turnaround",
                                        "gallery_delivery", "revenue", "satisfaction", "capacity"})
        self.assertEqual(metrics["shoots"]["comparison_label"], "Same period last year")
        self.assertEqual(metrics["editing_turnaround"]["value"], "Not available")
        self.assertIn("Editing timestamps are not currently recorded", metrics["editing_turnaround"]["excluded"])
        self.assertEqual(metrics["satisfaction"]["value"], "Not available")

    def test_capacity_is_insufficient_when_member_availability_is_incomplete(self):
        self.member.working_hours_end = None
        self.member.save(update_fields=["working_hours_end"])
        today = timezone.localdate()
        metrics = calculate_period_metrics(self.studio, [self.member], today - timedelta(days=1), today)
        self.assertIsNone(metrics["capacity"])
