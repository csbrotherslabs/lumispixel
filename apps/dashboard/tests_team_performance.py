from datetime import datetime, time, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientInvoice, ClientSession, InvoicePayment
from apps.dashboard.models import Review, StudioMembership
from apps.dashboard.team_performance import (_bucket_label, build_member_insights, calculate_period_metrics,
                                             team_performance_report)
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

    def test_trend_labels_use_cross_platform_date_formatting(self):
        day = timezone.localdate().replace(month=7, day=4)

        self.assertEqual(_bucket_label(day, "daily"), "Jul 4")
        self.assertEqual(_bucket_label(day, "weekly"), "Jul 4")
        self.assertEqual(_bucket_label(day, "monthly"), f"Jul {day.year}")
        self.assertEqual(_bucket_label(day, "quarterly"), f"Q3 {day.year}")

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

    def test_member_drill_down_is_scoped_and_contains_all_sections(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("photographer_workspace:team_performance_member",
                                           args=[self.member.pk]))
        self.assertEqual(response.status_code, 200)
        for heading in ("Overview", "Productivity", "Turnaround", "Contribution",
                        "Client Experience", "Activity", "Performance insights"):
            self.assertContains(response, heading)
        self.assertContains(response, "Capacity analysis needs availability data", count=0)

    def test_insights_are_deterministic_prioritized_and_limited(self):
        current = {"overdue": 3, "capacity": 90, "gallery_delivery": 8, "completion_rate": 70,
                   "shoots": 5, "eligible_assignments": 6, "satisfaction": 4.8}
        previous = {"overdue": 1, "capacity": 60, "gallery_delivery": 10, "completion_rate": 90,
                    "shoots": 2, "eligible_assignments": 3, "satisfaction": 4.2}
        team = {"gallery_delivery": 5}
        urls = {key: f"/{key}/" for key in ("bookings", "galleries", "schedule", "profile", "activity")}

        cards = build_member_insights(current, previous, team, urls)

        self.assertLessEqual(len(cards), 6)
        self.assertEqual(cards[0]["rule"], "overdue_rising")
        self.assertEqual(cards[0]["status"], "attention")
        self.assertTrue(all({"title", "explanation", "metric", "comparison", "status",
                             "action", "url"} <= card.keys() for card in cards))

    def test_shared_booking_revenue_stays_equally_allocated_when_member_filtered(self):
        colleague = StudioMembership.objects.create(
            studio=self.studio, invitation_email="second@example.com", role=StudioMembership.Role.PHOTOGRAPHER,
            status=StudioMembership.Status.ACTIVE)
        starts_at = timezone.now() - timedelta(days=1)
        booking = ClientSession.objects.create(
            photographer=self.studio, client=self.client_record, starts_at=starts_at,
            status=ClientSession.Status.COMPLETED)
        booking.assigned_members.add(self.member, colleague)
        invoice = ClientInvoice.objects.create(
            photographer=self.studio, client=self.client_record, booking=booking,
            total=Decimal("200.00"))
        InvoicePayment.objects.create(
            photographer=self.studio, invoice=invoice, amount=Decimal("200.00"),
            status=InvoicePayment.Status.COMPLETED, paid_at=starts_at)

        report = team_performance_report(self.studio, {"member": str(self.member.pk)})

        self.assertEqual(report["summary"]["revenue"], Decimal("100.00"))
        self.assertEqual(report["rows"][0]["revenue"], Decimal("100.00"))

    def test_manager_can_view_team_but_never_receives_financial_fields(self):
        manager_user = User.objects.create_user(
            email="manager@example.com", password="test-pass",
            primary_role=User.PrimaryRole.PHOTOGRAPHER)
        StudioMembership.objects.create(
            studio=self.studio, user=manager_user, role=StudioMembership.Role.MANAGER,
            status=StudioMembership.Status.ACTIVE)
        self.client.force_login(manager_user)

        response = self.client.get(reverse("photographer_workspace:team_performance"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Collected attributed revenue")
        self.assertContains(response, "No revenue records are requested or returned")
        self.assertTrue(all(row["revenue"] is None for row in response.context["export_rows"]))

    def test_photographer_is_denied_team_wide_performance(self):
        photographer = User.objects.create_user(
            email="assigned@example.com", password="test-pass",
            primary_role=User.PrimaryRole.PHOTOGRAPHER)
        StudioMembership.objects.create(
            studio=self.studio, user=photographer, role=StudioMembership.Role.PHOTOGRAPHER,
            status=StudioMembership.Status.ACTIVE)
        self.client.force_login(photographer)
        response = self.client.get(reverse("photographer_workspace:team_performance"))
        self.assertEqual(response.status_code, 403)

    def test_member_drilldown_rejects_membership_from_another_studio(self):
        other_owner = User.objects.create_user(
            email="other@example.com", password="test-pass",
            primary_role=User.PrimaryRole.PHOTOGRAPHER)
        other_studio = PhotographerProfile.objects.create(
            user=other_owner, slug="other-studio", onboarding_completed=True)
        outsider = StudioMembership.objects.create(
            studio=other_studio, user=other_owner, role=StudioMembership.Role.OWNER,
            status=StudioMembership.Status.ACTIVE)
        self.client.force_login(self.user)
        response = self.client.get(reverse("photographer_workspace:team_performance_member",
                                           args=[outsider.pk]))
        self.assertEqual(response.status_code, 404)

    def test_filters_solo_state_and_large_team_pagination(self):
        solo = team_performance_report(self.studio, {"role": StudioMembership.Role.OWNER})
        self.assertTrue(solo["solo_mode"])
        for index in range(12):
            StudioMembership.objects.create(
                studio=self.studio, invitation_email=f"person-{index}@example.com",
                role=StudioMembership.Role.PHOTOGRAPHER,
                status=StudioMembership.Status.ACTIVE,
                primary_location="North" if index % 2 else "South")

        report = team_performance_report(self.studio, {
            "role": StudioMembership.Role.PHOTOGRAPHER, "location": "North", "page": "1"})

        self.assertEqual(report["summary"]["members"], 6)
        self.assertTrue(all(row["role_key"] == StudioMembership.Role.PHOTOGRAPHER
                            and row["location"] == "North" for row in report["rows"]))
        all_report = team_performance_report(self.studio, {})
        self.assertEqual(all_report["page_obj"].paginator.num_pages, 2)
        self.assertEqual(len(all_report["export_rows"]), 13)
