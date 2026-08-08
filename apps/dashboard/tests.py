from django.core.management import call_command
from django.test import Client as TestClient, TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from io import BytesIO
from decimal import Decimal
from datetime import datetime, time, timedelta
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone

from apps.accounts.models import ClientProfile, PhotographerProfile, User
from apps.clients.models import Client, ClientActivity, ClientInvoice, ClientNote, ClientSession, ClientTask, InvoicePayment, Lead
from apps.galleries.models import AccessToken, Gallery, GalleryActivity, GalleryAnalyticsEvent, GalleryInvitation, GalleryPermission, GalleryPhoto, GallerySettings
from apps.ai_engine.models import AIJob, AIProcessingStatus
from apps.dashboard.models import StudioMembership
from apps.dashboard.views import GALLERY_STORAGE_LIMIT, WORKSPACE_MODULES
from apps.dashboard.analytics_overview import _analytics_insights, _short_date
from apps.dashboard.team_summary import authorized_studio, parse_team_filters, sessions_overlap
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection
from django.test.utils import CaptureQueriesContext
from unittest.mock import patch


def make_user(email, role=User.PrimaryRole.PHOTOGRAPHER):
    return User.objects.create_user(email=email, password="pass12345", primary_role=role, last_active_workspace=User.Workspace.PHOTOGRAPHER if role == User.PrimaryRole.PHOTOGRAPHER else User.Workspace.CLIENT, email_verified=True, account_status=User.AccountStatus.ACTIVE)


class PhotographerWorkspaceTests(TestCase):
    def make_photographer(self, completed=True, **profile_kwargs):
        user = make_user(profile_kwargs.pop("email", "photo@example.com"))
        profile = PhotographerProfile.objects.create(user=user, slug=profile_kwargs.pop("slug", "photo"), onboarding_completed=completed, **profile_kwargs)
        return user, profile

    def test_team_temporary_pages_routes_copy_and_navigation(self):
        user, _ = self.make_photographer(True, email="team@example.com", slug="team")
        self.client.force_login(user)
        pages = {
            "team_overview": ("Overview", "Monitor team workload, availability, assignments, capacity, and recent activity."),
            "team_members": ("Members", "Manage team members, invitations, profiles, roles, permissions, locations, working hours, and time off."),
            "team_performance": ("Performance", "Review productivity, booking contribution, revenue contribution, turnaround times, client experience, workload trends, and team activity."),
        }

        for route, (title, subtitle) in pages.items():
            url = reverse(f"photographer_workspace:{route}")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            if route == "team_overview":
                self.assertContains(response, '<h1 id="workspace-page-title">Team Overview</h1>', html=True)
                self.assertContains(response, "Monitor today’s availability, assignments, workload, and team activity.")
                for section in ("Today at a glance", "Today’s Team", "Today’s Assignments", "Upcoming Shoots", "Workload &amp; Capacity", "Team Alerts", "Recent Activity"):
                    self.assertContains(response, section)
            elif route == "team_members":
                self.assertContains(response, '<h1 id="workspace-page-title">Team Members</h1>', html=True)
                self.assertContains(response, "Manage your team, roles, access, and availability.")
            else:
                self.assertContains(response, '<h1 id="workspace-page-title">Team Performance</h1>', html=True)
                self.assertContains(response, "Review team productivity, contribution, turnaround, workload, and client experience over time.")
                for section in ("Team performance summary", "Performance over time",
                                "Productivity and completion", "Turnaround and delivery", "Revenue Contribution",
                                "Client experience", "Performance insights", "Recent performance activity"):
                    self.assertContains(response, section)
            self.assertContains(response, f'href="{url}" class="is-active" aria-current="page"')
            for child_route, (child_title, _) in pages.items():
                self.assertContains(response, reverse(f"photographer_workspace:{child_route}"))
                self.assertContains(response, child_title)
            if route == "team_performance":
                for removed_title in ("Schedule & Capacity", "Roles & Permissions", "Activity"):
                    self.assertNotContains(response, removed_title)

    def test_team_members_uses_owner_profile_and_honest_missing_sources(self):
        user, _ = self.make_photographer(True, email="owner@studio.example", slug="member-owner",
                                         display_name="Avery Owner", city="Portland", state="Oregon")
        self.client.force_login(user)
        url = reverse("photographer_workspace:team_members")
        response = self.client.get(url)

        self.assertContains(response, "Avery Owner")
        self.assertNotContains(response, "owner@studio.example")
        self.assertContains(response, "Portland, OR")
        for label in ("Team Members", "Active", "Pending"):
            self.assertContains(response, label)
        for removed in ("Build your studio team", "Active members", "Inactive members", "Everyone with access"):
            self.assertNotContains(response, removed)
        for role in ("Owner", "Studio Manager", "Photographer"):
            self.assertContains(response, role)
        self.assertNotContains(response, "Editor")
        self.assertNotContains(response, "Accountant")
        self.assertContains(response, "Working hours have not been configured.")
        self.assertContains(response, 'href="%s" class="is-active" aria-current="page"' % url)

        filtered = self.client.get(url, {"q": "nobody", "role": "photographer"})
        self.assertContains(filtered, "No members match your filters")

    def test_team_member_management_is_source_backed_and_protects_owner(self):
        owner, studio = self.make_photographer(True, email="manage-owner@example.com", slug="manage-owner")
        member_user = make_user("magdalene@example.com")
        member_user.first_name, member_user.last_name = "Magdalene", "Golomeke"
        member_user.save(update_fields=["first_name", "last_name"])
        membership = StudioMembership.objects.create(
            studio=studio, user=member_user, role=StudioMembership.Role.OWNER,
            status=StudioMembership.Status.ACTIVE, primary_location="Overland Park, KS",
        )
        client = Client.objects.create(photographer=studio, first_name="Taylor", last_name="Client")
        assignment = ClientSession.objects.create(
            photographer=studio, client=client, session_type="Brand session",
            starts_at=timezone.now() + timedelta(days=2), location="Main studio",
            status=ClientSession.Status.CONFIRMED,
        )
        assignment.assigned_members.add(membership)
        other_owner, other_studio = self.make_photographer(True, email="private-owner@example.com", slug="private-owner")
        private_client = Client.objects.create(photographer=other_studio, first_name="Private", last_name="Client")
        private_session = ClientSession.objects.create(
            photographer=other_studio, client=private_client, session_type="Private session",
            starts_at=timezone.now() + timedelta(days=1),
        )
        private_session.assigned_members.add(membership)
        self.client.force_login(owner)
        url = reverse("photographer_workspace:team_member_detail", args=[membership.pk])

        response = self.client.get(url)

        self.assertContains(response, '<main class="lpm-content lp-container lp-container--wide">')
        self.assertContains(response, "Magdalene Golomeke")
        self.assertContains(response, 'href="mailto:magdalene@example.com"')
        self.assertContains(response, "Overland Park, KS")
        for section in ("Profile", "Role &amp; Access", "Availability", "Upcoming assignments"):
            self.assertContains(response, section)
        for group in ("Clients", "Bookings", "Galleries", "Financial", "Growth", "Analytics", "Team", "Settings"):
            self.assertContains(response, group)
        self.assertContains(response, "Brand session")
        self.assertContains(response, "Taylor Client")
        self.assertNotContains(response, "Private session")
        self.assertNotContains(response, "Deactivate")
        self.assertNotContains(response, "Suspend")
        self.assertContains(response, "Owner account protected")

        changed = self.client.post(url, {
            "action": "save", "role": StudioMembership.Role.PHOTOGRAPHER,
            "availability": StudioMembership.Availability.UNKNOWN,
        })
        self.assertEqual(changed.status_code, 200)
        self.assertContains(changed, "Transfer ownership before changing the Owner role.")
        membership.refresh_from_db()
        self.assertEqual(membership.role, StudioMembership.Role.OWNER)

    def test_team_member_management_requires_manage_members_access(self):
        owner, studio = self.make_photographer(True, email="access-owner@example.com", slug="access-owner")
        viewer = make_user("viewer@example.com")
        target = make_user("target@example.com")
        StudioMembership.objects.create(
            studio=studio, user=viewer, role=StudioMembership.Role.PHOTOGRAPHER,
            status=StudioMembership.Status.ACTIVE,
        )
        target_membership = StudioMembership.objects.create(
            studio=studio, user=target, role=StudioMembership.Role.PHOTOGRAPHER,
            status=StudioMembership.Status.ACTIVE,
        )
        self.client.force_login(viewer)

        response = self.client.get(reverse("photographer_workspace:team_member_detail", args=[target_membership.pk]))

        self.assertEqual(response.status_code, 403)

    def test_team_overview_uses_owner_bookings_and_location_filter(self):
        user, profile = self.make_photographer(True, email="team-data@example.com", slug="team-data")
        other_user, other_profile = self.make_photographer(True, email="other-team@example.com", slug="other-team")
        client = Client.objects.create(photographer=profile, first_name="Taylor", last_name="Client", email="taylor@example.com")
        other_client = Client.objects.create(photographer=other_profile, first_name="Private", last_name="Client")
        today = timezone.localdate()
        starts = timezone.make_aware(datetime.combine(today, time.min)) + timedelta(hours=10)
        session = ClientSession.objects.create(photographer=profile, client=client, session_type="Brand session", starts_at=starts, location="Downtown", status=ClientSession.Status.CONFIRMED, duration_minutes=180)
        ClientSession.objects.create(photographer=other_profile, client=other_client, session_type="Private shoot", starts_at=starts, location="Downtown")
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:team_overview"), {"date": today.isoformat(), "location": "Downtown"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Brand session")
        self.assertContains(response, "Taylor Client")
        self.assertContains(response, "Capacity unavailable")
        self.assertContains(response, "No eight-hour day or availability is assumed")
        self.assertContains(response, reverse("photographer_workspace:booking_detail", args=[session.pk]))
        self.assertNotContains(response, "Private shoot")
        self.assertContains(response, "Not configured")

    def test_team_overview_workload_alerts_actions_and_team_activity_are_source_backed(self):
        user, profile = self.make_photographer(True, email="operations@example.com", slug="operations")
        client = Client.objects.create(photographer=profile, first_name="Alex", last_name="Client")
        today = timezone.localdate()
        starts = timezone.make_aware(datetime.combine(today, time(10)))
        booking = ClientSession.objects.create(
            photographer=profile, client=client, session_type="Portrait", starts_at=starts,
            duration_minutes=120, status=ClientSession.Status.CONFIRMED,
        )
        ClientActivity.objects.create(
            photographer=profile, client=client,
            event_type=ClientActivity.EventType.GALLERY_DELIVERED,
            description="Alex Client gallery delivered.",
        )
        ClientActivity.objects.create(
            photographer=profile, client=client,
            event_type=ClientActivity.EventType.NOTE_ADDED,
            description="This CRM-only event must not appear in team activity.",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:team_overview"), {"date": today.isoformat()})

        for heading in ("Shoots", "Scheduled", "Available", "Capacity", "Conflicts", "State"):
            self.assertContains(response, heading)
        for action in ("Invite Member", "View Schedule", "View Members"):
            self.assertContains(response, action)
        self.assertNotContains(response, "Assign Photographer")
        self.assertContains(response, "Unassigned shoot")
        self.assertContains(response, "Availability not configured")
        self.assertContains(response, "Portrait · Alex Client")
        self.assertContains(response, reverse("photographer_workspace:booking_detail", args=[booking.pk]))
        self.assertContains(response, "No recent team activity.")
        self.assertNotContains(response, "Saved team events.")
        self.assertNotContains(response, "New membership and assignment events will appear here.")
        self.assertNotContains(response, "Alex Client gallery delivered.")
        self.assertNotContains(response, "This CRM-only event must not appear in team activity.")

    def test_team_overview_status_kpis_availability_filters_and_states(self):
        user, _ = self.make_photographer(True, email="solo-team@example.com", slug="solo-team")
        self.client.force_login(user)
        url = reverse("photographer_workspace:team_overview")

        response = self.client.get(url)
        for label in ("Active Team Members", "Available Today", "On Assignment", "Unassigned shoots"):
            self.assertContains(response, label)
        for removed_label in ("Unavailable or on leave", "Team capacity utilization"):
            self.assertNotContains(response, removed_label)
        for detail in ("Member", "Availability", "Assignment", "Capacity", "Location", "Action"):
            self.assertContains(response, detail)
        self.assertContains(response, "Not configured")
        self.assertContains(response, "Unavailable")
        self.assertContains(response, "Configure")
        self.assertNotContains(response, "Assignment data unavailable")

        self.assertContains(self.client.get(url, {"q": "nobody"}), "No members match these filters")
        # Development-only state query parameters never alter production output.
        self.assertNotContains(self.client.get(url, {"state": "loading"}), "Loading team status")
        self.assertContains(self.client.get(url, {"state": "error"}), "Partial team data")
        self.assertContains(response, "Partial team data")
        self.assertContains(response, "Updated")

    def test_team_summary_authorization_and_filter_allow_lists(self):
        user, profile = self.make_photographer(True, email="authorized@example.com", slug="authorized")
        self.assertEqual(authorized_studio(user), profile)
        outsider = make_user("client-only@example.com", User.PrimaryRole.CLIENT)
        with self.assertRaises(PermissionDenied):
            authorized_studio(outsider)
        filters = parse_team_filters({"date": "not-a-date", "location": "x" * 300,
                                      "role": "administrator", "availability": "invented"})
        self.assertEqual(filters["date"], timezone.localdate())
        self.assertEqual(len(filters["location"]), 255)
        self.assertEqual(filters["role"], "")
        self.assertEqual(filters["availability"], "")

    def test_team_overview_unknown_location_does_not_widen_results(self):
        user, profile = self.make_photographer(True, email="location-scope@example.com", slug="location-scope")
        client = Client.objects.create(photographer=profile, first_name="Scoped", last_name="Client")
        starts = timezone.make_aware(datetime.combine(timezone.localdate(), time(9)))
        ClientSession.objects.create(photographer=profile, client=client, session_type="Scoped shoot",
                                     starts_at=starts, location="Studio A")
        self.client.force_login(user)
        response = self.client.get(reverse("photographer_workspace:team_overview"), {"location": "Other studio"})
        self.assertNotContains(response, "Scoped shoot")
        self.assertContains(response, "Your team has no shoots scheduled today.")

    def test_team_overlap_uses_duration_and_ignores_same_record(self):
        user, profile = self.make_photographer(True, email="overlap@example.com", slug="overlap")
        client = Client.objects.create(photographer=profile, first_name="Schedule", last_name="Client")
        starts = timezone.make_aware(datetime.combine(timezone.localdate(), time(9)))
        first = ClientSession.objects.create(photographer=profile, client=client, session_type="First", starts_at=starts, duration_minutes=60)
        overlapping = ClientSession.objects.create(photographer=profile, client=client, session_type="Second", starts_at=starts + timedelta(minutes=30), duration_minutes=30)
        adjacent = ClientSession.objects.create(photographer=profile, client=client, session_type="Third", starts_at=starts + timedelta(minutes=60), duration_minutes=30)
        self.assertTrue(sessions_overlap(first, overlapping))
        self.assertFalse(sessions_overlap(first, adjacent))
        self.assertFalse(sessions_overlap(first, first))

    def test_team_overview_assignment_details_attention_and_fourteen_day_window(self):
        user, profile = self.make_photographer(True, email="assignment-view@example.com", slug="assignment-view")
        client = Client.objects.create(photographer=profile, first_name="Avery", last_name="Stone")
        today = timezone.localdate()
        start = timezone.make_aware(datetime.combine(today, time(18)))
        first = ClientSession.objects.create(photographer=profile, client=client, session_type="Editorial", starts_at=start, duration_minutes=120, status=ClientSession.Status.CONFIRMED)
        ClientSession.objects.create(photographer=profile, client=client, session_type="Campaign", starts_at=start + timedelta(minutes=30), duration_minutes=60, location="Studio B", status=ClientSession.Status.CONFIRMED)
        future = ClientSession.objects.create(photographer=profile, client=client, session_type="Wedding", starts_at=start + timedelta(days=10), location="Garden", status=ClientSession.Status.CONFIRMED)
        ClientSession.objects.create(photographer=profile, client=client, session_type="Too distant", starts_at=start + timedelta(days=15), status=ClientSession.Status.CONFIRMED)
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:team_overview"), {"date": today.isoformat()})
        self.assertContains(response, "Editorial")
        self.assertContains(response, "Conflict")
        self.assertContains(response, "Overlaps another booking")
        self.assertContains(response, "Location missing")
        self.assertContains(response, "Photographer not assigned")
        self.assertNotContains(response, "Assign Photographer")
        self.assertContains(response, 'aria-label="View Editorial booking"')
        self.assertContains(response, "Next 14 days")
        self.assertContains(response, "Wedding")
        self.assertNotContains(response, "Too distant")
        self.assertContains(response, reverse("photographer_workspace:booking_detail", args=[first.pk]))
        self.assertContains(response, reverse("photographer_workspace:booking_detail", args=[future.pk]))

    def test_analytics_short_dates_are_cross_platform(self):
        self.assertEqual(_short_date(timezone.datetime(2026, 8, 1)), "Aug 1")

    def test_growth_overview_shell_navigation_filters_and_states(self):
        user, _ = self.make_photographer(True, email="growth@example.com", slug="growth")
        self.client.force_login(user)
        url = reverse("photographer_workspace:growth")

        response = self.client.get(url, {"range": "this_quarter", "compare": "1"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<h1 id="workspace-page-title">Growth Overview</h1>', html=True)
        self.assertContains(response, "Understand where clients come from, what converts, and how to grow your photography business.")
        self.assertContains(response, "Promote your business")
        self.assertContains(response, "Request reviews")
        self.assertContains(response, "Create referral link")
        self.assertContains(response, "Import leads")
        self.assertContains(response, "Export growth report")
        self.assertContains(response, 'value="this_quarter" selected')
        self.assertContains(response, 'name="compare" value="1" checked')
        self.assertContains(response, 'href="%s" class="is-active" aria-current="page"' % url)
        for heading in ("Growth metrics", "Lead funnel", "Lead sources", "Service performance", "Reviews", "Referrals", "Client retention", "Growth opportunities", "Recent activity"):
            self.assertContains(response, heading)
        self.assertContains(self.client.get(url, {"state": "loading"}), "Loading your growth overview")
        self.assertContains(self.client.get(url, {"state": "empty"}), "Your growth overview is ready")
        self.assertContains(self.client.get(url, {"state": "permission"}), "You don’t have permission")
        self.assertContains(self.client.get(url, {"state": "error"}), "Growth insights could not be loaded")
        section_states = self.client.get(url, {
            "funnel_state": "error", "sources_state": "loading",
            "services_state": "error", "reviews_state": "loading",
            "activity_state": "error",
        })
        self.assertContains(section_states, "Lead funnel is unavailable")
        self.assertContains(section_states, "Service performance is unavailable")
        self.assertContains(section_states, "Recent activity is unavailable")
        self.assertContains(section_states, "lp-skeleton--list", count=2)
        self.assertContains(response, '<input type="hidden" name="compare" value="1">', html=True)

    def test_analytics_foundation_sections_filters_and_states(self):
        user, _ = self.make_photographer(True, email="analytics-page@example.com", slug="analytics-page")
        self.client.force_login(user)
        url = reverse("photographer_workspace:analytics")
        response = self.client.get(url, {"range": "this_quarter", "compare": "previous_year"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Understand business performance, trends, risks, and opportunities")
        self.assertContains(response, "Photographer Workspace")
        self.assertContains(response, 'class="lpa-page lp-container lp-container--wide"')
        self.assertContains(response, 'value="this_quarter" selected')
        self.assertContains(response, 'value="previous_year" selected')
        for heading in ("Executive Overview", "Revenue &amp; Sales", "Clients &amp; Retention", "Bookings &amp; Demand", "Galleries / Engagement", "Capacity &amp; Operations", "Insights &amp; Recommended Actions"):
            self.assertContains(response, heading)
        self.assertContains(response, "Booking Patterns")
        self.assertContains(response, "More booking history is needed to identify seasonality.")
        self.assertContains(response, "More booking activity is needed to identify busy and quiet periods.")
        self.assertContains(response, "Reschedule history is not currently tracked.")
        for heading in ("New versus returning clients", "Client acquisition trend", "Leads by source",
                        "Conversion rate by lead source", "Client value by segment", "Repeat-booking funnel",
                        "Top client locations", "Referral performance", "High-value client segments"):
            self.assertContains(response, heading)
        for metric in ("New clients", "Returning clients", "Repeat booking rate", "Average client value",
                       "Referral rate", "Average client spend", "Lead response time", "Lead-to-booking conversion"):
            self.assertContains(response, metric)
        self.assertContains(response, "names, contact details, and individual activity are intentionally excluded")
        for heading in ("Business Health and Summary", "Business Health", "Category contributions", "Business Summary"):
            self.assertContains(response, heading)
        self.assertContains(response, "No machine learning is used.")
        self.assertContains(response, "Missing categories are excluded, not scored as zero.")
        for metric in ("Total bookings", "Booking conversion rate", "Cancellation rate", "Reschedule rate",
                       "Average lead-to-book time", "Average booking value", "Schedule utilization", "No-show rate"):
            self.assertContains(response, metric)
        for report in ("Bookings over time", "Bookings by service", "Bookings by package", "Bookings by weekday",
                       "Bookings by time of day", "Booking seasonality", "Cancellation and reschedule trends",
                       "Booking status distribution", "Busy and quiet periods", "Top Services"):
            self.assertContains(response, report)
        for report in ("Gallery views over time", "Engagement by gallery", "Engagement by service type",
                       "Favorites and downloads trend", "Most active galleries", "Gallery delivery turnaround",
                       "Client access and invitation completion", "Store conversion where gallery commerce exists",
                       "Top Galleries"):
            self.assertContains(response, report)
        for metric in ("Total gallery views", "Unique gallery visitors", "Average gallery engagement",
                       "Favorites or selections", "Downloads", "Shares", "Store orders",
                       "Average gallery delivery time", "Client access completion", "Expired or inactive galleries"):
            self.assertContains(response, metric)
        for column in ("Published date", "Views", "Favorites", "Downloads", "Shares", "Engagement rate", "Status"):
            self.assertContains(response, column)
        self.assertContains(response, "visitor identifiers, invitation emails, and individual activity are never displayed")
        self.assertContains(response, "Open filtered Bookings")
        self.assertContains(response, "Open Schedule")
        self.assertContains(response, "not a booking calendar")
        self.assertContains(response, "Team analytics needs more operational data")
        self.assertContains(response, "revenue alone is never treated as employee performance")
        self.assertContains(response, "View Team")
        for state, copy in (("loading", "Loading analytics"), ("error", "Analytics could not be loaded"), ("permission", "You don’t have permission"), ("empty", "Your analytics workspace is ready")):
            self.assertContains(self.client.get(url, {"state": state}), copy)

    def test_analytics_drilldowns_and_csv_export(self):
        user, _ = self.make_photographer(True, email="analytics-export@example.com", slug="analytics-export")
        self.client.force_login(user)
        url = reverse("photographer_workspace:analytics")
        page = self.client.get(url)
        self.assertContains(page, "Metric definition")
        self.assertContains(page, "Historical trend")
        self.assertContains(page, "Print / save PDF")
        self.assertContains(page, "Export approved metrics for the active date range and filters")
        self.assertContains(page, "Open the current analytics view in the browser print dialog")
        export = self.client.get(url, {"export": "csv"})
        self.assertEqual(export.status_code, 200)
        self.assertEqual(export["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("Total revenue", export.content.decode("utf-8-sig"))

    def test_analytics_insights_are_deterministic_ranked_and_limited(self):
        current = {"revenue": Decimal("1500"), "net": Decimal("1450"), "bookings": 8,
                   "clients": 5, "conversion": Decimal("10"), "average": Decimal("500"),
                   "views": 20, "repeat": Decimal("10")}
        previous = {**current, "revenue": Decimal("1000"), "conversion": Decimal("35"),
                    "repeat": Decimal("30")}
        urls = {key: f"/{key}/" for key in ("financial", "bookings", "growth", "galleries", "clients")}
        customer = {"sources": [
            {"label": "Google", "value": 6, "conversion": 60.0, "url": "/google/"},
            {"label": "Social", "value": 5, "conversion": 20.0, "url": "/social/"},
        ]}
        gallery = {"raw": {"views": 20, "engagement": 5.0}}
        operations = {"raw": {"overdue_tasks": 9, "late_deliveries": 4, "utilization": 90.0}}

        first = _analytics_insights(current, previous, Decimal("50"), Decimal("3000"),
            Decimal("1500"), Decimal("30"), customer, gallery, operations, urls, "USD")
        second = _analytics_insights(current, previous, Decimal("50"), Decimal("3000"),
            Decimal("1500"), Decimal("30"), customer, gallery, operations, urls, "USD")

        self.assertEqual(first, second)
        self.assertEqual(len(first), 6)
        self.assertEqual([item["score"] for item in first], sorted(
            (item["score"] for item in first), reverse=True))
        self.assertEqual(first[0]["category"], "Payment risk")
        for item in first:
            self.assertTrue(item["title"] and item["explanation"] and item["metric"])
            self.assertTrue(item["severity"] and item["action"] and item["url"])

    def test_analytics_insights_empty_state_requires_activity(self):
        current = {key: Decimal("0") for key in
                   ("revenue", "net", "bookings", "clients", "conversion", "average", "views", "repeat")}
        urls = {key: f"/{key}/" for key in ("financial", "bookings", "growth", "galleries", "clients")}
        insights = _analytics_insights(current, None, None, Decimal("0"), Decimal("0"), None,
            {"sources": []}, {"raw": {"views": 0, "engagement": 0}},
            {"raw": {"overdue_tasks": 0, "late_deliveries": 0, "utilization": 0}}, urls, "USD")
        self.assertEqual(insights, [])

    def test_analytics_overview_uses_owner_records_and_preserves_filters(self):
        user, profile = self.make_photographer(True, email="analytics-data@example.com", slug="analytics-data")
        client = Client.objects.create(photographer=profile, first_name="Maya", client_type=Client.ClientType.INDIVIDUAL)
        booking = ClientSession.objects.create(photographer=profile, client=client, session_type="Portrait",
            location="Studio A", starts_at=timezone.now(), status=ClientSession.Status.CONFIRMED, booking_value=1200)
        invoice = ClientInvoice.objects.create(photographer=profile, client=client, booking=booking, total=1200)
        InvoicePayment.objects.create(photographer=profile, invoice=invoice, amount=1200, processor_fee=36)
        gallery = Gallery.objects.create(photographer=profile, client=client, name="Maya portraits", slug="maya-portraits", status=Gallery.Status.PUBLISHED)
        GalleryAnalyticsEvent.objects.create(photographer=profile, gallery=gallery,
            event_type=GalleryAnalyticsEvent.EventType.VIEW, visitor_identifier="opaque-visitor")
        GalleryAnalyticsEvent.objects.create(photographer=profile, gallery=gallery,
            event_type=GalleryAnalyticsEvent.EventType.FAVORITE, visitor_identifier="opaque-visitor")
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:analytics"), {
            "range": "30_days", "compare": "none", "location": "Studio A", "service": "Portrait",
            "client_type": Client.ClientType.INDIVIDUAL, "booking_status": ClientSession.Status.CONFIRMED,
            "gallery_status": Gallery.Status.PUBLISHED,
        })

        self.assertEqual(response.status_code, 200)
        for label in ("Total revenue", "Net revenue", "Total bookings", "New clients", "Lead-to-booking conversion",
                      "Average booking value", "Gallery views", "Repeat booking rate"):
            self.assertContains(response, label)
        self.assertContains(response, "$1,200")
        self.assertContains(response, "$1,164")
        self.assertContains(response, "Not compared")
        self.assertNotContains(response, "+0.0%")
        self.assertContains(response, "Location:")
        self.assertContains(response, "Studio A")
        self.assertContains(response, 'data-remove-filter="location"')
        self.assertContains(response, 'aria-label="Date range"')
        self.assertContains(response, 'aria-haspopup="dialog"')
        self.assertContains(response, "Payment collection health")
        self.assertContains(response, "100.0% of invoiced value collected")
        self.assertContains(response, "Healthy")
        self.assertContains(response, "Rules, not AI")
        for label in ("Gross revenue", "Revenue per client", "Revenue per booking", "Outstanding balance trend",
                      "Payment collection time", "Refund rate"):
            self.assertContains(response, label)
        for report in ("Revenue by service", "Revenue by package", "Revenue by location",
                       "Revenue by photographer or team member", "Revenue by lead source", "Revenue by client type",
                       "Revenue by booking status", "Revenue by month or season"):
            self.assertContains(response, report)
        for chart in ("Revenue trend", "Revenue mix by service", "Revenue by team member",
                      "Average booking value trend", "Revenue concentration"):
            self.assertContains(response, chart)
        self.assertContains(response, "Expenses, profit, and margins are not inferred")
        self.assertContains(response, "Financial Overview")
        self.assertContains(response, "Filtered Transactions")
        self.assertContains(response, "Maya portraits")
        self.assertContains(response, "100.0%")
        self.assertNotContains(response, "opaque-visitor")

    def test_anonymous_client_and_incomplete_access_rules(self):
        url = reverse("photographer_workspace:dashboard")
        self.assertRedirects(self.client.get(url), f"{reverse('accounts:login')}?next={url}", fetch_redirect_response=False)
        client_user = make_user("client@example.com", User.PrimaryRole.CLIENT)
        ClientProfile.objects.create(user=client_user, onboarding_completed=True)
        self.client.force_login(client_user)
        self.assertRedirects(self.client.get(url), reverse("clients:dashboard"), fetch_redirect_response=False)
        self.client.logout()
        incomplete, _ = self.make_photographer(False, email="incomplete@example.com", slug="incomplete")
        self.client.force_login(incomplete)
        self.assertRedirects(self.client.get(url), reverse("photographers:setup-dashboard"), fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse("photographer_workspace:galleries")), reverse("photographers:setup-dashboard"), fetch_redirect_response=False)

    def test_gallery_settings_persist_validate_and_are_owner_scoped(self):
        user, profile = self.make_photographer(True, email="settings@example.com", slug="settings")
        _, other = self.make_photographer(True, email="settings-other@example.com", slug="settings-other")
        gallery = Gallery.objects.create(photographer=profile, name="Coastal Wedding", slug="coastal-wedding")
        private_gallery = Gallery.objects.create(photographer=other, name="Private", slug="private")
        self.client.force_login(user)
        url = reverse("photographer_workspace:gallery_workspace", args=[gallery.pk])
        page = self.client.get(url, {"tab": "settings"})
        self.assertContains(page, "Gallery Settings")
        self.assertContains(page, "Permanently Delete Gallery")
        payload = {
            "action": "save_settings", "general-name": "Coastal Celebration", "general-description": "Client delivery",
            "general-event_date": "2026-08-10", "general-client": "", "general-status": Gallery.Status.PUBLISHED,
            "general-visibility": Gallery.Visibility.PRIVATE, "general-expiration_date": "2026-09-01",
            "settings-accent_color": "#123ABC", "settings-watermark_position": GallerySettings.WatermarkPosition.CENTER,
            "settings-theme": GallerySettings.Theme.EDITORIAL, "settings-allow_downloads": "on", "settings-zip_downloads": "on",
            "settings-download_limit": "12", "settings-enable_favorites": "on", "settings-enable_slideshow": "on",
            "settings-gallery_url": "coastal-client", "settings-meta_title": "Coastal client gallery",
            "settings-meta_description": "A private photography gallery for our coastal celebration.",
        }
        response = self.client.post(url, payload)
        self.assertRedirects(response, f"{url}?tab=settings")
        gallery.refresh_from_db()
        self.assertEqual(gallery.name, "Coastal Celebration")
        self.assertEqual(gallery.settings.download_limit, 12)
        self.assertEqual(gallery.settings.gallery_url, "coastal-client")
        self.assertEqual(self.client.get(reverse("photographer_workspace:gallery_workspace", args=[private_gallery.pk]), {"tab": "settings"}).status_code, 404)

    def test_completed_photographer_dashboard_and_post_login_destination(self):
        user, _ = self.make_photographer(True, business_name="Lumis Studio", display_name="Alex Lens", website_theme=PhotographerProfile.WebsiteTheme.MODERN_STUDIO)
        user.first_name = "Alex"
        user.save(update_fields=["first_name"])
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse("accounts:post-login-redirect")), reverse("photographer_workspace:dashboard"), fetch_redirect_response=False)
        response = self.client.get(reverse("photographer_workspace:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="dashboard-heading"')
        self.assertNotContains(response, '<h2>Dashboard</h2>', html=True)
        self.assertContains(response, "Good ")
        self.assertContains(response, "Alex.")
        self.assertContains(response, "Your schedule is clear")
        self.assertNotContains(response, "Business key performance indicators")
        self.assertContains(response, "Upcoming schedule")
        self.assertContains(response, "Recent activity")
        self.assertContains(response, "Gallery delivery queue")
        self.assertContains(response, "Quick actions")
        self.assertContains(response, "Gallery storage")
        self.assertNotContains(response, "Your Website Preview")
        self.assertNotContains(response, "Help and Resources")
        self.assertContains(response, f'href="{reverse("core:index")}" aria-label="LumisPixel home"')

    def test_missing_images_and_invalid_theme_fallback_do_not_error(self):
        user, profile = self.make_photographer(True, email="fallback@example.com", slug="fallback", display_name="Fallback Photo")
        PhotographerProfile.objects.filter(pk=profile.pk).update(website_theme="legacy")
        self.client.force_login(user)
        response = self.client.get(reverse("photographer_workspace:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fallback Photo")
        self.assertContains(response, "Dashboard")

    def test_navigation_urls_and_placeholders_resolve(self):
        user, _ = self.make_photographer(True, email="nav@example.com", slug="nav")
        self.client.force_login(user)
        for module in WORKSPACE_MODULES:
            url = reverse(f"photographer_workspace:{module['url_name']}")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, module["title"])
            if module["key"] not in {"dashboard", "crm", "leads", "clients", "galleries", "all_galleries", "gallery_upload_queue", "ai_processing", "bookings", "financial_overview"}:
                self.assertContains(response, "Back to Dashboard")

    def test_bookings_dashboard_structure_navigation_and_states(self):
        user, profile = self.make_photographer(True, email="bookings@example.com", slug="bookings")
        client = Client.objects.create(photographer=profile, first_name="Maya", last_name="Cole", email="maya@example.com")
        ClientSession.objects.create(photographer=profile, client=client, session_type="Portrait", starts_at=timezone.now() + timezone.timedelta(days=2), status=ClientSession.Status.CONFIRMED)
        self.client.force_login(user)
        url = reverse("photographer_workspace:bookings")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Photographer Workspace")
        self.assertContains(response, "Overview")
        self.assertContains(response, "View Schedule")
        self.assertContains(response, "Manage upcoming sessions, confirmations, payments, and scheduling activity.")
        self.assertContains(response, "New Booking")
        self.assertContains(response, 'data-event-form-open="booking"')
        self.assertContains(response, 'data-event-form-layer hidden')
        self.assertContains(response, 'data-event-form-drawer role="dialog"')
        self.assertContains(response, 'name="event_type" value="booking" checked')
        self.assertContains(response, "New Lead")
        self.assertContains(response, "Upcoming Bookings")
        self.assertContains(response, "Bookings This Month")
        self.assertContains(response, "Pending Confirmations")
        self.assertContains(response, "Today's Schedule")
        self.assertContains(response, "Booking Revenue")
        self.assertContains(response, "30 days")
        self.assertContains(response, "90 days")
        self.assertContains(response, "6 months")
        self.assertContains(response, "12 months")
        self.assertContains(response, "Booking Stage Summary")
        self.assertContains(response, "Confirmed")
        self.assertContains(response, "Recent Activity")
        self.assertContains(response, "No booking activity yet")
        self.assertContains(response, "Block Time")
        self.assertContains(response, "Schedule Consultation")
        self.assertContains(response, "Today's Focus")
        self.assertContains(response, "All caught up for today.")
        self.assertContains(response, "Maya Cole")
        self.assertContains(response, f'href="{url}" class="is-active"')
        self.assertContains(self.client.get(url, {"state": "loading"}), "Loading content")
        self.assertContains(self.client.get(url, {"state": "error"}), "Bookings could not be loaded")

    def test_contracts_live_in_the_booking_detail_workspace(self):
        user, profile = self.make_photographer(True, email="contract-booking@example.com", slug="contract-booking")
        client = Client.objects.create(photographer=profile, first_name="Maya", last_name="Cole", email="maya.contract@example.com")
        booking = ClientSession.objects.create(
            photographer=profile, client=client, session_type="Portrait",
            starts_at=timezone.now() + timezone.timedelta(days=2),
            status=ClientSession.Status.CONFIRMED,
        )
        self.client.force_login(user)
        detail_url = reverse("photographer_workspace:booking_detail", args=[booking.pk])

        dashboard = self.client.get(reverse("photographer_workspace:bookings"))
        self.assertNotContains(dashboard, "Sample data")
        self.assertNotContains(dashboard, 'href="/workspace/contracts/"')
        with self.assertRaises(Resolver404):
            resolve("/workspace/contracts/")

        contract = self.client.get(detail_url, {"tab": "contract"})
        self.assertContains(contract, "Send contract")
        self.assertContains(contract, "Send reminder")
        self.assertContains(contract, "View signatures")
        self.assertContains(contract, "Download signed PDF")
        response = self.client.post(detail_url, {"action": "send_contract"})
        self.assertRedirects(response, f"{detail_url}?tab=contract#contract", fetch_redirect_response=False)

    def test_schedule_route_controls_and_navigation(self):
        user, profile = self.make_photographer(True, email="schedule@example.com", slug="schedule")
        client = Client.objects.create(photographer=profile, first_name="Maya", last_name="Cole", email="maya.schedule@example.com")
        ClientSession.objects.create(
            photographer=profile, client=client, session_type="Portrait",
            starts_at=timezone.now() + timezone.timedelta(days=2),
            status=ClientSession.Status.CONFIRMED,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:schedule"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Business Hub")
        self.assertContains(response, "View bookings, manage availability, and organize photography work.")
        self.assertContains(response, "New Booking")
        self.assertContains(response, "Block Time")
        self.assertContains(response, "Add Consultation")
        self.assertContains(response, "Add Editing Time")
        self.assertContains(response, "Add Vacation")
        self.assertContains(response, "Create Mini Session")
        self.assertContains(response, "Booking List")
        self.assertContains(response, "Today")
        self.assertContains(response, "Schedule", count=None)
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, 'data-event-drawer role="dialog"')
        self.assertContains(response, 'data-schedule-event="schedule-event-0"')
        self.assertContains(response, "Open Full Booking")
        self.assertContains(response, '"contract_status": "Not tracked"')
        self.assertContains(response, '"label": "Mark Complete"')
        self.assertContains(response, '"label": "Cancel Booking"')
        self.assertContains(response, "Today’s Schedule")
        self.assertContains(response, "Upcoming Shoots")
        self.assertContains(response, "Scheduling Alerts")
        self.assertContains(response, 'data-schedule-summary')
        self.assertContains(response, "Preparation incomplete")

        list_response = self.client.get(reverse("photographer_workspace:schedule"), {"view": "list"})
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "Booking List view")

    def test_schedule_filters_persist_across_views_and_filter_bookings(self):
        user, profile = self.make_photographer(True, email="filters@example.com", slug="filters")
        client = Client.objects.create(photographer=profile, first_name="Maya", last_name="Cole", email="maya.filters@example.com")
        starts_at = timezone.now() + timezone.timedelta(days=2)
        ClientSession.objects.create(photographer=profile, client=client, session_type="Portrait", location="Studio A", starts_at=starts_at, status=ClientSession.Status.CONFIRMED)
        ClientSession.objects.create(photographer=profile, client=client, session_type="Wedding", location="Garden", starts_at=starts_at, status=ClientSession.Status.CANCELLED)
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:schedule"), {
            "view": "agenda", "q": "Studio A", "session_type": "Portrait", "status": "confirmed",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Maya Cole")
        self.assertNotContains(response, "Wedding ·")
        self.assertContains(response, "3 active")
        self.assertContains(response, "q=Studio+A", count=None)
        self.assertContains(response, "Save View")
        self.assertContains(response, "Show Availability")

        cancelled = self.client.get(reverse("photographer_workspace:schedule"), {
            "view": "list", "status": "cancelled", "show_cancelled": "1",
        })
        self.assertContains(cancelled, "Wedding")
        self.assertContains(cancelled, "Cancelled")

    def test_bookings_schedule_can_mark_an_owned_session_complete(self):
        user, profile = self.make_photographer(True, email="schedule@example.com", slug="schedule")
        client = Client.objects.create(photographer=profile, first_name="Maya", last_name="Cole", email="maya@example.com")
        session = ClientSession.objects.create(
            photographer=profile, client=client, session_type="Portrait consultation",
            starts_at=timezone.now(), status=ClientSession.Status.CONFIRMED,
        )
        self.client.force_login(user)
        response = self.client.post(reverse("photographer_workspace:bookings"), {
            "action": "mark_complete", "session_id": session.pk,
        })
        self.assertRedirects(response, reverse("photographer_workspace:bookings"))
        session.refresh_from_db()
        self.assertEqual(session.status, ClientSession.Status.COMPLETED)

    def test_shared_booking_drawer_creates_a_scoped_booking(self):
        user, profile = self.make_photographer(True, email="create-booking@example.com", slug="create-booking")
        client = Client.objects.create(
            photographer=profile, first_name="Avery", last_name="Stone",
            email="avery@example.com",
        )
        _other_user, other = self.make_photographer(True, email="other-booking@example.com", slug="other-booking")
        private_client = Client.objects.create(photographer=other, first_name="Private", last_name="Client")
        self.client.force_login(user)
        url = reverse("photographer_workspace:bookings")

        page = self.client.get(url)
        self.assertContains(page, f'<option value="{client.pk}">Avery Stone</option>')
        self.assertNotContains(page, "Private Client")
        response = self.client.post(url, {
            "action": "create_booking", "client": client.pk,
            "session_type": "Family portrait", "start_date": "2026-08-12",
            "start_time": "09:00", "end_date": "2026-08-12", "end_time": "10:30",
            "location": "Studio A", "booking_status": "confirmed", "price": "425.00",
        }, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 201)
        booking = ClientSession.objects.get(photographer=profile, client=client)
        self.assertEqual(booking.duration_minutes, 90)
        self.assertEqual(booking.booking_value, Decimal("425.00"))
        self.assertEqual(booking.status, ClientSession.Status.CONFIRMED)
        self.assertIn(str(booking.pk), response.json()["booking_url"])

        rejected = self.client.post(url, {
            "action": "create_booking", "client": private_client.pk,
            "session_type": "Private", "start_date": "2026-08-12",
            "start_time": "09:00", "end_date": "2026-08-12", "end_time": "10:00",
            "booking_status": "tentative",
        }, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(ClientSession.objects.filter(photographer=profile).count(), 1)

    def test_schedule_inspector_actions_follow_booking_state_and_are_scoped(self):
        user, profile = self.make_photographer(True, email="inspector@example.com", slug="inspector")
        _other_user, other = self.make_photographer(True, email="other-inspector@example.com", slug="other-inspector")
        client = Client.objects.create(photographer=profile, first_name="Maya", last_name="Cole", email="maya@example.com")
        other_client = Client.objects.create(photographer=other, first_name="Private", last_name="Client")
        session = ClientSession.objects.create(photographer=profile, client=client, session_type="Portrait", starts_at=timezone.now(), status=ClientSession.Status.CONFIRMED)
        private = ClientSession.objects.create(photographer=other, client=other_client, session_type="Private", starts_at=timezone.now())
        self.client.force_login(user)

        complete = self.client.post(reverse("photographer_workspace:booking_action", args=[session.pk]), {"action": "mark_complete"})
        self.assertRedirects(complete, reverse("photographer_workspace:schedule"))
        session.refresh_from_db()
        self.assertEqual(session.status, ClientSession.Status.COMPLETED)
        completed_page = self.client.get(reverse("photographer_workspace:schedule"), {"status": "completed", "show_completed": "1"})
        self.assertNotContains(completed_page, '"label": "Mark Complete"')
        self.assertContains(completed_page, '"label": "Create Gallery"')
        self.assertNotContains(completed_page, '"label": "Reschedule"')

        self.assertEqual(self.client.post(reverse("photographer_workspace:booking_action", args=[private.pk]), {"action": "cancel"}).status_code, 404)
        cancel = self.client.post(reverse("photographer_workspace:booking_action", args=[session.pk]), {"action": "cancel"})
        self.assertRedirects(cancel, reverse("photographer_workspace:schedule"))
        session.refresh_from_db()
        self.assertEqual(session.status, ClientSession.Status.CANCELLED)

    def test_schedule_move_previews_conflicts_and_saves_duration(self):
        user, profile = self.make_photographer(True, email="move@example.com", slug="move")
        client = Client.objects.create(photographer=profile, first_name="Maya", last_name="Cole")
        start = timezone.now() + timezone.timedelta(days=3)
        moving = ClientSession.objects.create(photographer=profile, client=client, session_type="Portrait", starts_at=start)
        ClientSession.objects.create(photographer=profile, client=client, session_type="Wedding", starts_at=start + timezone.timedelta(hours=1))
        self.client.force_login(user)
        url = reverse("photographer_workspace:reschedule_session", args=[moving.pk])

        conflict = self.client.post(url, data={"starts_at": start.isoformat(), "duration_minutes": 120, "preview": True}, content_type="application/json")
        self.assertTrue(conflict.json()["blocking"])
        self.assertEqual(conflict.json()["checks"][0]["key"], "conflict")

        new_start = start + timezone.timedelta(days=2)
        saved = self.client.post(url, data={"starts_at": new_start.isoformat(), "duration_minutes": 150, "preview": False}, content_type="application/json")
        self.assertEqual(saved.status_code, 200)
        moving.refresh_from_db()
        self.assertEqual(moving.duration_minutes, 150)
        self.assertEqual(moving.starts_at, new_start)

    def test_schedule_move_is_studio_scoped(self):
        user, _profile = self.make_photographer(True, email="owner@example.com", slug="owner")
        _other_user, other = self.make_photographer(True, email="other-move@example.com", slug="other-move")
        client = Client.objects.create(photographer=other, first_name="Private", last_name="Client")
        session = ClientSession.objects.create(photographer=other, client=client, session_type="Private", starts_at=timezone.now())
        self.client.force_login(user)
        response = self.client.post(reverse("photographer_workspace:reschedule_session", args=[session.pk]), data={}, content_type="application/json")
        self.assertEqual(response.status_code, 404)

    def test_ai_processing_center_creates_scoped_jobs_and_supports_actions(self):
        user, profile = self.make_photographer(True, email="ai@example.com", slug="ai")
        _, other = self.make_photographer(True, email="other-ai@example.com", slug="other-ai")
        gallery = Gallery.objects.create(photographer=profile, name="AI Wedding", slug="ai-wedding", image_count=80)
        private_gallery = Gallery.objects.create(photographer=other, name="Private AI Gallery", slug="private-ai")
        self.client.force_login(user)

        page = self.client.get(reverse("photographer_workspace:ai_processing"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Monitor and manage AI tasks for every gallery.")
        self.assertContains(page, "Face Detection")
        self.assertContains(page, "Search Indexing")
        self.assertNotContains(page, "Private AI Gallery")

        response = self.client.post(reverse("photographer_workspace:ai_processing"), {
            "gallery_ids": [gallery.pk, private_gallery.pk],
            "task_types": [AIJob.TaskType.FACE_DETECTION, AIJob.TaskType.BLUR_DETECTION],
        })
        self.assertRedirects(response, reverse("photographer_workspace:ai_processing"))
        self.assertEqual(AIJob.objects.for_photographer(profile).count(), 2)
        job = AIJob.objects.get(photographer=profile, task_type=AIJob.TaskType.FACE_DETECTION)
        self.assertEqual(job.progress.total_images, 80)
        self.assertEqual(job.status, AIJob.Status.QUEUED)

        job.status = AIJob.Status.FAILED
        job.error_summary = "Worker unavailable"
        job.save()
        retry = self.client.post(reverse("photographer_workspace:ai_job_action", args=[job.pk]), {"action": "retry"})
        self.assertRedirects(retry, reverse("photographer_workspace:ai_processing"))
        job.refresh_from_db()
        self.assertEqual(job.status, AIJob.Status.QUEUED)
        cancel = self.client.post(reverse("photographer_workspace:ai_job_action", args=[job.pk]), {"action": "cancel"})
        self.assertRedirects(cancel, reverse("photographer_workspace:ai_processing"))
        job.refresh_from_db()
        self.assertEqual(job.status, AIJob.Status.CANCELLED)

    def test_gallery_pages_render_with_active_navigation_and_scoped_records(self):
        user, profile = self.make_photographer(True, email="gallery@example.com", slug="gallery-photo")
        _, other = self.make_photographer(True, email="other-gallery@example.com", slug="other-gallery-photo")
        gallery = Gallery.objects.create(photographer=profile, name="Summer Portraits", slug="summer-portraits", status=Gallery.Status.UPLOADING, image_count=24)
        private_gallery = Gallery.objects.create(photographer=other, name="Private Collection", slug="private-collection")
        self.client.force_login(user)

        expected_pages = [
            ("galleries", "Galleries", "galleries"),
            ("all_galleries", "All Galleries", "all_galleries"),
            ("gallery_upload_queue", "Upload Queue", "all_galleries"),
        ]
        for url_name, heading, active_url_name in expected_pages:
            response = self.client.get(reverse(f"photographer_workspace:{url_name}"))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, heading)
            self.assertContains(response, f'href="{reverse(f"photographer_workspace:{active_url_name}")}" class="is-active"')
            self.assertContains(response, "Summer Portraits")
            self.assertNotContains(response, "Private Collection")

            if url_name == "gallery_upload_queue":
                self.assertContains(response, '<nav class="lpw-breadcrumb" aria-label="Breadcrumb">')
                self.assertContains(response, 'class="lp-gallery-picker__controls"')

        dashboard = self.client.get(reverse("photographer_workspace:galleries"))
        self.assertContains(dashboard, "Manage gallery delivery, client activity, uploads, and storage.")
        self.assertContains(dashboard, "Active Galleries")
        self.assertContains(dashboard, "Ready to Deliver")
        self.assertContains(dashboard, "Delivery Pipeline")
        self.assertContains(dashboard, "Recent Client Activity")
        self.assertContains(dashboard, "Storage Overview")
        self.assertContains(dashboard, "Upcoming Deadlines")

        detail = self.client.get(reverse("photographer_workspace:gallery_workspace", args=[gallery.pk]))
        self.assertContains(detail, "Gallery summary")
        self.assertContains(detail, "Upload progress")
        self.assertContains(self.client.get(reverse("photographer_workspace:gallery_workspace", args=[gallery.pk]), {"tab": "photos"}), "Search photos")
        self.assertEqual(self.client.get(reverse("photographer_workspace:gallery_workspace", args=[private_gallery.pk])).status_code, 404)

    def test_client_access_settings_and_secure_invitations(self):
        user, profile = self.make_photographer(True, email="access@example.com", slug="access")
        gallery = Gallery.objects.create(photographer=profile, name="Client Delivery", slug="client-delivery")
        self.client.force_login(user)
        url = reverse("photographer_workspace:gallery_workspace", args=[gallery.pk])

        page = self.client.get(url, {"tab": "client-access"})
        self.assertContains(page, "Control who can access this gallery.")
        self.assertContains(page, "Gallery Visibility")
        self.assertContains(page, "Purchase Prints")
        self.assertContains(page, "Client Invitations")

        saved = self.client.post(url, {
            "action": "save_access", "visibility": Gallery.Visibility.PUBLIC,
            "view_gallery": "on", "favorite_photos": "on", "automatic_gallery_lock": "on",
            "watermark": GalleryPermission.Watermark.ALL, "expiration_date": "2027-01-10",
        })
        self.assertRedirects(saved, f"{url}?tab=client-access")
        gallery.refresh_from_db()
        permissions = gallery.permissions
        self.assertEqual(gallery.visibility, Gallery.Visibility.PUBLIC)
        self.assertTrue(permissions.automatic_gallery_lock)
        self.assertFalse(permissions.download_images)
        self.assertEqual(permissions.watermark, GalleryPermission.Watermark.ALL)

        invited = self.client.post(url, {"action": "invite", "client_name": "Avery Stone", "email": "AVERY@example.com"})
        self.assertRedirects(invited, f"{url}?tab=client-access")
        invitation = GalleryInvitation.objects.get(gallery=gallery, email="avery@example.com")
        token = AccessToken.objects.get(invitation=invitation)
        self.assertEqual(len(token.token_hash), 64)
        self.assertNotIn("avery", token.token_hash)

        self.client.post(url, {"action": "disable", "invitation_id": invitation.pk})
        invitation.refresh_from_db()
        token.refresh_from_db()
        self.assertEqual(invitation.status, GalleryInvitation.Status.DISABLED)
        self.assertIsNotNone(token.revoked_at)

    def test_gallery_upload_validates_images_and_scopes_media(self):
        user, profile = self.make_photographer(True, email="upload@example.com", slug="upload")
        other_user, other = self.make_photographer(True, email="upload-other@example.com", slug="upload-other")
        gallery = Gallery.objects.create(photographer=profile, name="Secure", slug="secure")
        image = BytesIO()
        Image.new("RGB", (8, 8), "red").save(image, "JPEG")
        self.client.force_login(user)
        response = self.client.post(reverse("photographer_workspace:gallery_upload_queue"), {
            "gallery": gallery.pk, "files": SimpleUploadedFile("photo.jpg", image.getvalue(), content_type="image/jpeg")
        })
        self.assertEqual(response.status_code, 201)
        photo = GalleryPhoto.objects.get(gallery=gallery)
        self.assertEqual(self.client.get(reverse("photographer_workspace:gallery_photo_media", args=[photo.pk])).status_code, 200)
        invalid = self.client.post(reverse("photographer_workspace:gallery_upload_queue"), {
            "gallery": gallery.pk, "files": SimpleUploadedFile("fake.jpg", b"not an image", content_type="image/jpeg")
        })
        self.assertEqual(invalid.status_code, 400)
        self.client.force_login(other_user)
        self.assertEqual(self.client.get(reverse("photographer_workspace:gallery_photo_media", args=[photo.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("photographer_workspace:gallery_upload_queue"), {"gallery": gallery.pk}).status_code, 404)

    def test_gallery_upload_rejects_files_when_workspace_storage_is_insufficient(self):
        user, profile = self.make_photographer(True, email="storage-upload@example.com", slug="storage-upload")
        gallery = Gallery.objects.create(
            photographer=profile, name="Nearly Full", slug="nearly-full",
            storage_used=GALLERY_STORAGE_LIMIT - 1,
        )
        image = BytesIO()
        Image.new("RGB", (8, 8), "blue").save(image, "JPEG")
        self.client.force_login(user)

        response = self.client.post(reverse("photographer_workspace:gallery_upload_queue"), {
            "gallery": gallery.pk,
            "files": SimpleUploadedFile("photo.jpg", image.getvalue(), content_type="image/jpeg"),
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"][0]["error"], "Not enough storage to upload these files.")
        self.assertFalse(GalleryPhoto.objects.filter(gallery=gallery).exists())

    def test_gallery_create_edit_filters_and_bulk_actions(self):
        user, profile = self.make_photographer(True, email="gallery-crud@example.com", slug="gallery-crud")
        client = Client.objects.create(photographer=profile, first_name="Maya", last_name="Cole")
        self.client.force_login(user)

        create_page = self.client.get(reverse("photographer_workspace:create_gallery"))
        self.assertContains(create_page, "Set up the gallery now. Add photos and delivery settings next.")
        self.assertContains(create_page, 'class="workspace-form-page lp-container lp-add-lead lp-add-gallery lp-clients-main-width"')
        self.assertContains(create_page, 'aria-label="Breadcrumb"')
        self.assertContains(create_page, f'href="{reverse("photographer_workspace:all_galleries")}">Galleries</a>')
        self.assertContains(create_page, "Gallery Details")
        self.assertContains(create_page, "Cover Image")
        self.assertContains(create_page, "Publishing &amp; Access")
        self.assertLess(create_page.content.index(b"Gallery Details"), create_page.content.index(b"Client experience"))
        self.assertLess(create_page.content.index(b"Client experience"), create_page.content.index(b"Publishing &amp; Access"))
        self.assertContains(create_page, 'aria-label="Live gallery preview"')
        self.assertContains(create_page, 'data-cover-remove')
        self.assertContains(create_page, '<span>Create Gallery</span>', count=1, html=True)

        create = self.client.post(reverse("photographer_workspace:create_gallery"), {
            "name": "Maya & Rowan", "client": client.pk, "event_date": "2026-08-12",
            "description": "A summer celebration", "status": Gallery.Status.DRAFT,
            "visibility": Gallery.Visibility.PASSWORD, "expiration_date": "2026-10-01",
        })
        gallery = Gallery.objects.get(name="Maya & Rowan")
        self.assertRedirects(create, reverse("photographer_workspace:gallery_workspace", args=[gallery.pk]))
        self.assertEqual(gallery.slug, "maya-rowan")
        self.assertIsNotNone(gallery.expires_at)

        filtered = self.client.get(reverse("photographer_workspace:all_galleries"), {"q": "Maya", "client": client.pk, "status": "draft"})
        self.assertContains(filtered, "Maya &amp; Rowan")
        self.assertContains(filtered, 'data-gallery-view="grid"')
        self.assertContains(filtered, 'data-gallery-view="list"')
        self.assertContains(filtered, "Search gallery name or client")
        self.assertContains(filtered, "More filters")
        self.assertContains(filtered, "result")

        empty_user, empty_profile = self.make_photographer(True, email="gallery-empty@example.com", slug="gallery-empty")
        self.client.force_login(empty_user)
        empty = self.client.get(reverse("photographer_workspace:all_galleries"))
        self.assertContains(empty, "Create your first gallery")
        self.assertContains(empty, "Build a beautiful space to upload, organize, and deliver photos to your clients.")
        self.assertContains(empty, "Upload Photos")

        self.client.force_login(user)

        self.client.post(reverse("photographer_workspace:gallery_actions"), {"gallery_ids": [gallery.pk], "action": "publish"})
        gallery.refresh_from_db()
        self.assertEqual(gallery.status, Gallery.Status.PUBLISHED)
        self.assertIsNotNone(gallery.published_at)

        self.client.post(reverse("photographer_workspace:gallery_actions"), {"gallery_ids": [gallery.pk], "action": "archive"})
        gallery.refresh_from_db()
        self.assertEqual(gallery.status, Gallery.Status.ARCHIVED)
        self.assertIsNotNone(gallery.archived_at)
        self.assertNotContains(self.client.get(reverse("photographer_workspace:all_galleries")), "Maya &amp; Rowan")
        self.assertContains(self.client.get(reverse("photographer_workspace:gallery_archive")), "Maya &amp; Rowan")

        restored = self.client.post(reverse("photographer_workspace:gallery_archive_actions"), {
            "gallery_ids": [gallery.pk], "action": "restore",
        })
        self.assertRedirects(restored, reverse("photographer_workspace:gallery_archive"))
        gallery.refresh_from_db()
        self.assertEqual(gallery.status, Gallery.Status.DRAFT)
        self.assertEqual(gallery.visibility, Gallery.Visibility.PRIVATE)
        self.assertIsNone(gallery.archived_at)

    def test_archive_actions_enforce_photographer_ownership(self):
        user, profile = self.make_photographer(True, email="archive@example.com", slug="archive")
        _, other = self.make_photographer(True, email="archive-other@example.com", slug="archive-other")
        gallery = Gallery.objects.create(photographer=profile, name="Owned Archive", slug="owned-archive")
        private = Gallery.objects.create(photographer=other, name="Private Archive", slug="private-archive")
        self.client.force_login(user)
        self.client.post(reverse("photographer_workspace:gallery_archive_actions"), {
            "gallery_ids": [gallery.pk, private.pk], "action": "archive", "archive_reason": Gallery.ArchiveReason.COMPLETED,
            "retention_days": "365", "disable_public_access": "on", "confirm_archive": "on",
        })
        gallery.refresh_from_db(); private.refresh_from_db()
        self.assertEqual(gallery.status, Gallery.Status.ARCHIVED)
        self.assertEqual(gallery.archive_reason, Gallery.ArchiveReason.COMPLETED)
        self.assertEqual(private.status, Gallery.Status.DRAFT)
        self.assertNotContains(self.client.get(reverse("photographer_workspace:gallery_archive")), "Private Archive")

    def test_activity_timeline_filters_exports_and_enforces_ownership(self):
        user, profile = self.make_photographer(True, email="activity@example.com", slug="activity")
        _, other = self.make_photographer(True, email="private-activity@example.com", slug="private-activity")
        gallery = Gallery.objects.create(photographer=profile, name="Activity Gallery", slug="activity-gallery")
        private_gallery = Gallery.objects.create(photographer=other, name="Private Activity", slug="private-activity")
        GalleryActivity.objects.create(photographer=profile, gallery=gallery, actor=user,
            actor_type=GalleryActivity.ActorType.PHOTOGRAPHER, event_type=GalleryActivity.EventType.GALLERY_UPDATED,
            title="Gallery updated", description="A visible timeline event.")
        self.client.force_login(user)
        url = reverse("photographer_workspace:gallery_workspace", args=[gallery.pk])

        page = self.client.get(url, {"tab": "activity"})
        self.assertContains(page, "Review everything that has happened in this gallery.")
        self.assertContains(page, "Client Interactions")
        self.assertContains(page, "A visible timeline event.")
        self.assertContains(page, "View details")
        no_results = self.client.get(url, {"tab": "activity", "activity_q": "missing"})
        self.assertContains(no_results, "No activity matches your filters")
        exported = self.client.get(url, {"tab": "activity", "export": "csv"})
        self.assertEqual(exported["Content-Type"], "text/csv")
        self.assertIn(b"Gallery updated", exported.content)
        self.assertEqual(self.client.get(reverse("photographer_workspace:gallery_workspace", args=[private_gallery.pk]), {"tab": "activity"}).status_code, 404)

    def test_album_crud_workspace_and_owner_isolation(self):
        from apps.galleries.models import Album, AlbumPhoto

        user, profile = self.make_photographer(True, email="album-crud@example.com", slug="album-crud")
        _, other = self.make_photographer(True, email="album-other@example.com", slug="album-other")
        gallery = Gallery.objects.create(photographer=profile, name="Wedding", slug="wedding")
        private_gallery = Gallery.objects.create(photographer=other, name="Private", slug="private")
        private_album = Album.objects.create(gallery=private_gallery, name="Private album")
        self.client.force_login(user)

        created = self.client.post(reverse("photographer_workspace:create_album", args=[gallery.pk]), {
            "name": "Golden Hour", "description": "Warm portraits", "visibility": Album.Visibility.PUBLIC, "display_order": 2,
        })
        album = Album.objects.get(gallery=gallery)
        self.assertRedirects(created, reverse("photographer_workspace:album_workspace", args=[album.pk]))
        albums_page = self.client.get(reverse("photographer_workspace:gallery_workspace", args=[gallery.pk]), {"tab": "albums"})
        self.assertContains(albums_page, "Organize galleries into beautiful collections.")
        self.assertContains(albums_page, "Golden Hour")
        self.assertContains(albums_page, "Public Albums")
        self.assertEqual(self.client.get(reverse("photographer_workspace:album_workspace", args=[private_album.pk])).status_code, 404)

        duplicate = self.client.post(reverse("photographer_workspace:album_action", args=[album.pk]), {"action": "duplicate"})
        self.assertEqual(duplicate.status_code, 302)
        self.assertTrue(Album.objects.filter(gallery=gallery, name="Golden Hour Copy").exists())

    def test_clients_workspace_uses_scoped_data_and_directory_controls(self):
        user, profile = self.make_photographer(True, email="directory@example.com", slug="directory")
        _, other = self.make_photographer(True, email="other-directory@example.com", slug="other-directory")
        visible = Client.objects.create(photographer=profile, first_name="Avery", last_name="Stone", email="avery@example.com", tags=["VIP"], client_type=Client.ClientType.INDIVIDUAL)
        ClientInvoice.objects.create(photographer=profile, client=visible, total="900.00", amount_paid="250.00", status=ClientInvoice.Status.SENT)
        Client.objects.create(photographer=other, first_name="Private", last_name="Record")
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:clients"), {"tag": "VIP"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Manage client relationships, projects, payments, and galleries.")
        self.assertContains(response, "Avery Stone")
        self.assertContains(response, "USD 650.00")
        self.assertNotContains(response, "Private Record")
        self.assertContains(response, 'data-client-view="list"')
        self.assertContains(response, 'data-client-view="grid"')

    def test_client_detail_actions_tabs_alerts_and_isolation(self):
        user, profile = self.make_photographer(True, email="detail@example.com", slug="detail")
        _, other = self.make_photographer(True, email="private-detail@example.com", slug="private-detail")
        client = Client.objects.create(photographer=profile, first_name="Avery", last_name="Stone", email="avery@example.com", tags=["VIP"], preferred_contact_method=Client.ContactMethod.EMAIL)
        private = Client.objects.create(photographer=other, first_name="Private", last_name="Client")
        ClientInvoice.objects.create(photographer=profile, client=client, total="500", amount_paid="100", status=ClientInvoice.Status.SENT, due_date="2020-01-01")
        ClientSession.objects.create(photographer=profile, client=client, session_type="Portrait", starts_at=timezone.now() + timezone.timedelta(days=2), status=ClientSession.Status.CONFIRMED)
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:client_detail", args=[client.pk]))
        self.assertContains(response, "Contact details")
        self.assertContains(response, "Outstanding balance")
        self.assertContains(response, "Overdue invoices")
        self.assertContains(response, "Unsigned contracts")
        self.assertContains(response, "Galleries awaiting delivery")
        self.assertContains(response, "USD 400.00")
        self.assertEqual(self.client.get(reverse("photographer_workspace:client_detail", args=[private.pk])).status_code, 404)

        self.client.post(reverse("photographer_workspace:add_client_note", args=[client.pk]), {"content": "Prefers mornings"})
        self.client.post(reverse("photographer_workspace:add_client_task", args=[client.pk]), {"title": "Send guide", "priority": "high"})
        self.assertTrue(ClientNote.objects.filter(client=client, content="Prefers mornings").exists())
        self.assertTrue(ClientTask.objects.filter(client=client, title="Send guide").exists())
        self.client.post(reverse("photographer_workspace:client_archive_restore", args=[client.pk]))
        client.refresh_from_db()
        self.assertEqual(client.status, Client.Status.ARCHIVED)
        self.client.post(reverse("photographer_workspace:client_archive_restore", args=[client.pk]))
        client.refresh_from_db()
        self.assertEqual(client.status, Client.Status.ACTIVE)
        self.assertTrue(ClientActivity.objects.filter(client=client, event_type=ClientActivity.EventType.CLIENT_RESTORED).exists())

    def test_client_mutations_require_csrf(self):
        user, profile = self.make_photographer(True, email="client-csrf@example.com", slug="client-csrf")
        client = Client.objects.create(photographer=profile, first_name="Protected", email="protected@example.com")
        csrf_client = TestClient(enforce_csrf_checks=True)
        csrf_client.force_login(user)
        self.assertEqual(csrf_client.post(reverse("photographer_workspace:client_archive_restore", args=[client.pk])).status_code, 403)
        client.refresh_from_db()
        self.assertEqual(client.status, Client.Status.ACTIVE)

    def test_crm_dashboard_uses_only_logged_in_photographers_records(self):
        user, profile = self.make_photographer(True, email="crm@example.com", slug="crm")
        other_user, other = self.make_photographer(True, email="other-crm@example.com", slug="other-crm")
        Lead.objects.create(photographer=profile, first_name="Visible", status=Lead.Status.NEW)
        Lead.objects.create(photographer=other, first_name="Private", status=Lead.Status.NEW)
        client = Client.objects.create(photographer=profile, first_name="Taylor")
        ClientInvoice.objects.create(photographer=profile, client=client, total="500.00", amount_paid="125.00", status=ClientInvoice.Status.SENT)
        other_client = Client.objects.create(photographer=other, first_name="Other")
        ClientInvoice.objects.create(photographer=other, client=other_client, total="900.00", status=ClientInvoice.Status.SENT)

        self.client.force_login(user)
        response = self.client.get(reverse("photographer_workspace:crm"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="lp-crm-page lp-clients-main-width"')
        self.assertContains(response, "Manage inquiries, relationships, consultations, and follow-ups from one place.")
        self.assertContains(response, "Visible")
        self.assertNotContains(response, "Private")
        self.assertContains(response, "Active Leads")
        self.assertContains(response, "?status=new")

    def test_active_navigation_item_is_correct(self):
        user, _ = self.make_photographer(True, email="active@example.com", slug="active")
        self.client.force_login(user)
        response = self.client.get(reverse("photographer_workspace:analytics"))
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, "Analytics")

    def test_grouped_navigation_and_profile_menu(self):
        user, _ = self.make_photographer(True, email="grouped@example.com", slug="grouped")
        user.first_name = "Avery"
        user.last_name = "Stone"
        user.save(update_fields=["first_name", "last_name"])
        self.client.force_login(user)
        response = self.client.get(reverse("photographer_workspace:crm"))
        self.assertContains(response, "Growth")
        self.assertNotContains(response, "Business Growth")
        self.assertContains(response, 'aria-controls="nav-group-1"')
        self.assertContains(response, 'aria-label="Clients" data-tooltip="Clients"')
        self.assertContains(response, 'href="/photographer/workspace/leads/"')
        self.assertContains(response, "Avery Stone")
        self.assertContains(response, "Photographer")
        self.assertContains(response, "Business Settings")
        self.assertContains(response, "Sign Out")

    def test_sidebar_uses_simplified_business_hub_navigation(self):
        user, _ = self.make_photographer(True, email="simple-nav@example.com", slug="simple-nav")
        self.client.force_login(user)
        response = self.client.get(reverse("photographer_workspace:dashboard"))

        for label in ("Clients", "Bookings", "Galleries", "Financial", "Growth", "Analytics", "Team", "Settings"):
            self.assertContains(response, label)
        for route_name in ("crm", "leads", "clients", "bookings", "schedule", "galleries", "all_galleries", "financial_overview", "transactions", "growth", "analytics", "team", "settings"):
            self.assertContains(response, f'href="{reverse(f"photographer_workspace:{route_name}")}"')
        for obsolete_label in ("Business Growth", "Gallery Archive", "Upload Queue", "AI Processing", "Marketing", "Reviews", "Referrals", "Invoices", "Payments", "Revenue", "Contracts"):
            self.assertNotContains(response, f">{obsolete_label}<")

    def test_legacy_financial_and_growth_pages_keep_consolidated_nav_active(self):
        user, _ = self.make_photographer(True, email="legacy-nav@example.com", slug="legacy-nav")
        self.client.force_login(user)

        invoice_page = self.client.get(reverse("photographer_workspace:invoices"))
        self.assertContains(invoice_page, f'href="{reverse("photographer_workspace:financial_overview")}" class="is-active"')
        marketing_page = self.client.get(reverse("photographer_workspace:marketing"))
        self.assertContains(marketing_page, f'href="{reverse("photographer_workspace:growth")}" class="is-active"')

    def test_financial_overview_renders_shell_header_actions_and_states(self):
        user, _ = self.make_photographer(True, email="finance-shell@example.com", slug="finance-shell")
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:financial_overview"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="lp-financial-overview"')
        self.assertNotContains(response, 'class="lp-container lp-financial-overview"')
        self.assertContains(response, "Financial Overview")
        self.assertContains(response, "Track revenue, payments, balances, and financial activity.")
        self.assertContains(response, "Create Invoice")
        self.assertContains(response, "View Transactions")
        for action in ("Record payment", "Issue refund", "Add credit"):
            self.assertContains(response, action)
        self.assertContains(response, "Your financial overview is ready")
        self.assertContains(response, "Create an invoice or receive your first payment to begin tracking business performance.")
        self.assertNotContains(response, "Revenue Performance")
        self.assertNotContains(response, "No upcoming payments")
        self.assertContains(response, f'href="{reverse("photographer_workspace:financial_overview")}" class="is-active"')

        loading_url = f'{reverse("photographer_workspace:financial_overview")}?state=loading'
        error_url = f'{reverse("photographer_workspace:financial_overview")}?state=error'
        loading = self.client.get(loading_url)
        self.assertContains(loading, "Loading financial overview")
        for metric in ("Total Revenue", "Collected", "Outstanding", "Overdue"):
            self.assertContains(loading, metric)
        self.assertContains(self.client.get(error_url), "Financial activity could not be loaded")

    def test_client_cannot_access_module_url(self):
        client_user = make_user("client-module@example.com", User.PrimaryRole.CLIENT)
        ClientProfile.objects.create(user=client_user, onboarding_completed=True)
        self.client.force_login(client_user)
        self.assertRedirects(self.client.get(reverse("photographer_workspace:orders")), reverse("clients:dashboard"), fetch_redirect_response=False)

    def test_system_checks_pass(self):
        call_command("check")

    def test_crm_create_complete_and_convert_workflow(self):
        user, profile = self.make_photographer(True, email="workflow@example.com", slug="workflow")
        self.client.force_login(user)
        response = self.client.post(reverse("photographer_workspace:add_lead"), {
            "first_name": "Jordan", "last_name": "Lee", "email": "jordan@example.com",
        })
        self.assertRedirects(response, reverse("photographer_workspace:crm"))
        lead = Lead.objects.get(photographer=profile, email="jordan@example.com")
        self.assertTrue(ClientActivity.objects.filter(lead=lead, event_type=ClientActivity.EventType.LEAD_CREATED).exists())

        response = self.client.post(reverse("photographer_workspace:create_task"), {
            "title": "Call Jordan", "priority": ClientTask.Priority.HIGH, "lead": lead.pk,
        })
        self.assertRedirects(response, reverse("photographer_workspace:crm"))
        task = ClientTask.objects.get(photographer=profile)
        self.client.post(reverse("photographer_workspace:complete_task", args=[task.pk]))
        task.refresh_from_db()
        self.assertEqual(task.status, ClientTask.Status.COMPLETED)

        self.client.post(reverse("photographer_workspace:convert_lead", args=[lead.pk]))
        lead.refresh_from_db()
        converted = Client.objects.get(converted_lead=lead)
        self.assertEqual(converted.photographer, profile)
        self.assertEqual(lead.status, Lead.Status.BOOKED)
        self.assertTrue(ClientActivity.objects.filter(lead=lead, client=converted, event_type=ClientActivity.EventType.LEAD_CONVERTED).exists())
        self.client.post(reverse("photographer_workspace:convert_lead", args=[lead.pk]))
        self.assertEqual(Client.objects.filter(converted_lead=lead).count(), 1)

    def test_crm_client_creation_and_ownership_protection(self):
        user, profile = self.make_photographer(True, email="create@example.com", slug="create")
        other_user, other = self.make_photographer(True, email="private@example.com", slug="private")
        private_task = ClientTask.objects.create(photographer=other, lead=Lead.objects.create(photographer=other, first_name="Private"), title="Private")
        self.client.force_login(user)
        self.client.post(reverse("photographer_workspace:add_client"), {"first_name": "Sam", "email": "sam@example.com", "status": Client.Status.ACTIVE})
        self.assertTrue(Client.objects.filter(photographer=profile, email="sam@example.com").exists())
        self.assertEqual(self.client.post(reverse("photographer_workspace:complete_task", args=[private_task.pk])).status_code, 404)
        private_task.refresh_from_db()
        self.assertEqual(private_task.status, ClientTask.Status.OPEN)

    def test_add_client_form_renders_crud_system_and_saves_extended_details(self):
        user, profile = self.make_photographer(True, email="form@example.com", slug="form")
        self.client.force_login(user)
        response = self.client.get(reverse("photographer_workspace:add_client"))
        self.assertContains(response, 'class="workspace-form-page lp-container lp-add-lead lp-clients-main-width"')
        self.assertContains(response, 'class="form-section-card"')
        self.assertContains(response, 'data-upload-dropzone')
        self.assertContains(response, 'data-submit-button')
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(response, f'href="{reverse("photographer_workspace:crm")}">CRM</a>')
        self.assertContains(response, 'class="lp-button lp-button--primary lp-button--md"')
        self.assertContains(response, '<h1 class="lp-page-title" id="workspace-page-title">Add Client</h1>', count=1, html=True)

        response = self.client.post(reverse("photographer_workspace:add_client"), {
            "first_name": "Avery", "email": "avery@example.com", "status": Client.Status.ACTIVE,
            "address": "10 Main Street", "city": "Portland", "state_province": "Oregon",
            "postal_code": "97205", "country": "United States", "tags_input": "VIP,Portrait",
            "notes": "Prefers morning sessions.",
        })
        self.assertRedirects(response, reverse("photographer_workspace:crm"))
        client = Client.objects.get(photographer=profile, email="avery@example.com")
        self.assertEqual(client.address, "10 Main Street\nPortland\nOregon\n97205\nUnited States")
        self.assertEqual(client.tags, ["VIP", "Portrait"])
        self.assertEqual(client.notes.get().content, "Prefers morning sessions.")

    def test_add_lead_form_uses_crud_design_system(self):
        user, profile = self.make_photographer(True, email="lead-form@example.com", slug="lead-form")
        self.client.force_login(user)
        response = self.client.get(reverse("photographer_workspace:add_lead"))
        self.assertContains(response, 'class="workspace-form-page lp-container lp-add-lead lp-clients-main-width"')
        self.assertContains(response, "Contact Details")
        self.assertContains(response, "Inquiry Details")
        self.assertContains(response, 'aria-label="Live lead summary"')
        self.assertContains(response, "Capture a new inquiry and the details needed for follow-up.")
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(response, f'href="{reverse("photographer_workspace:crm")}">CRM</a>')
        self.assertContains(response, f'<span aria-hidden="true">{profile.default_currency}</span>', html=True)
        self.assertContains(response, "Lead Summary")
        self.assertContains(response, 'data-lead-progress')
        self.assertContains(response, 'data-summary-followup')
        self.assertContains(response, f'data-currency="{profile.default_currency}"')
        self.assertContains(response, "Start entering lead details to build the profile.")
        self.assertContains(response, "Readiness")
        self.assertContains(response, "Contact")
        self.assertContains(response, "Not scheduled")
        self.assertNotContains(response, "Lead tips")
        self.assertNotContains(response, "Quick tips")
        self.assertNotContains(response, "Start strong")
        self.assertContains(response, 'data-submit-button')
        self.assertContains(response, 'class="lp-button lp-button--primary lp-button--md"')
        self.assertContains(response, "Save Lead")
        self.assertContains(response, '<h1 class="lp-page-title" id="workspace-page-title">Add Lead</h1>', count=1, html=True)

        invalid = self.client.post(reverse("photographer_workspace:add_lead"), {"first_name": ""})
        self.assertContains(invalid, 'aria-invalid="true"')
        self.assertContains(invalid, 'aria-describedby="id_first_name-error"')

        created = self.client.post(reverse("photographer_workspace:add_lead"), {"first_name": "Avery", "email": "avery-lead@example.com"}, follow=True)
        self.assertRedirects(created, reverse("photographer_workspace:crm"))
        self.assertContains(created, "Lead created.")

    def test_crm_mutations_require_authentication_and_post(self):
        user, profile = self.make_photographer(True, email="secure@example.com", slug="secure")
        lead = Lead.objects.create(photographer=profile, first_name="Secure")
        url = reverse("photographer_workspace:convert_lead", args=[lead.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(user)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.logout()
        self.client.post(url)
        self.assertFalse(Client.objects.filter(converted_lead=lead).exists())

    def test_leads_workspace_uses_scoped_real_data_and_metrics(self):
        user, profile = self.make_photographer(True, email="pipeline@example.com", slug="pipeline")
        _, other = self.make_photographer(True, email="other-pipeline@example.com", slug="other-pipeline")
        Lead.objects.create(photographer=profile, first_name="Morgan", last_name="Ray", event_type="Wedding", estimated_value="2400", lead_source="Referral")
        Lead.objects.create(photographer=profile, first_name="Casey", status=Lead.Status.BOOKED, estimated_value="1600")
        Lead.objects.create(photographer=other, first_name="Private", estimated_value="9000")
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:leads"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<nav class="lpw-breadcrumb" aria-label="Breadcrumb">')
        self.assertContains(response, '<strong aria-current="page">Leads</strong>', html=True)
        self.assertContains(response, 'class="lp-leads-quick-filter"', count=2)
        self.assertContains(response, "Track inquiries, manage follow-ups, and move opportunities toward booking.")
        self.assertContains(response, "Morgan Ray")
        self.assertNotContains(response, "Private")
        self.assertContains(response, "USD 2,400")
        self.assertContains(response, "50.0%")
        self.assertContains(response, 'data-lead-view="board"')
        self.assertContains(response, 'data-stage="proposal_sent"')

        self.assertContains(
            response,
            f'<a href="{reverse("photographer_workspace:add_lead")}" class="lp-button lp-button--primary lp-button--md">',
        )
        self.assertContains(response, '<span>Add Lead</span>', html=True)

    def test_lead_filters_followups_dates_and_source_aggregations_are_real(self):
        user, profile = self.make_photographer(True, email="filter-leads@example.com", slug="filter-leads")
        today = timezone.localdate()
        visible = Lead.objects.create(
            photographer=profile, first_name="Urgent", event_type="Wedding", lead_source="Referral",
            estimated_value="2500", next_follow_up=today - timedelta(days=1),
        )
        Lead.objects.create(
            photographer=profile, first_name="Future", event_type="Portrait", lead_source="Search",
            estimated_value="900", next_follow_up=today + timedelta(days=4),
        )
        booked = Lead.objects.create(
            photographer=profile, first_name="Booked", lead_source="Referral", status=Lead.Status.BOOKED,
            estimated_value="5000",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:leads"), {
            "q": "Urgent", "event_type": "Wedding", "source": "Referral", "follow_up": "overdue",
            "created_from": today.isoformat(), "created_to": today.isoformat(),
        })

        self.assertContains(response, visible.first_name)
        self.assertNotContains(response, "Future")
        self.assertEqual(response.context["result_count"], 1)
        referral = next(row for row in response.context["source_rows"] if row["lead_source"] == "Referral")
        self.assertEqual((referral["count"], referral["booked"], referral["pipeline_value"]), (2, 1, Decimal("2500")))
        self.assertEqual(referral["conversion"], 50)

    def test_moving_to_booked_uses_conversion_and_lost_requires_reason_flow(self):
        user, profile = self.make_photographer(True, email="workflow-leads@example.com", slug="workflow-leads")
        lead = Lead.objects.create(photographer=profile, first_name="Conversion", email="conversion@example.com")
        self.client.force_login(user)

        self.client.post(reverse("photographer_workspace:update_lead_status", args=[lead.pk]), {
            "status": Lead.Status.BOOKED, "next": reverse("photographer_workspace:leads"),
        })
        lead.refresh_from_db()
        self.assertEqual(lead.status, Lead.Status.BOOKED)
        self.assertTrue(Client.objects.filter(photographer=profile, converted_lead=lead).exists())

        second = Lead.objects.create(photographer=profile, first_name="Loss")
        self.client.post(reverse("photographer_workspace:update_lead_status", args=[second.pk]), {
            "status": Lead.Status.LOST, "next": reverse("photographer_workspace:leads"),
        })
        second.refresh_from_db()
        self.assertEqual(second.status, Lead.Status.NEW)
        self.client.post(reverse("photographer_workspace:mark_lead_lost", args=[second.pk]), {"reason": "Timing"})
        second.refresh_from_db()
        self.assertEqual((second.status, second.lost_reason), (Lead.Status.LOST, "Timing"))

    def test_lead_stage_and_bulk_updates_are_scoped(self):
        user, profile = self.make_photographer(True, email="move@example.com", slug="move")
        _, other = self.make_photographer(True, email="other-move@example.com", slug="other-move")
        own = Lead.objects.create(photographer=profile, first_name="Move Me")
        private = Lead.objects.create(photographer=other, first_name="Do Not Move")
        self.client.force_login(user)
        self.client.post(reverse("photographer_workspace:update_lead_status", args=[own.pk]), {"status": Lead.Status.CONTACTED, "next": reverse("photographer_workspace:leads")})
        self.client.post(reverse("photographer_workspace:bulk_update_leads"), {"lead_ids": [own.pk, private.pk], "action": Lead.Status.CONSULTATION})
        own.refresh_from_db()
        private.refresh_from_db()
        self.assertEqual(own.status, Lead.Status.CONSULTATION)
        self.assertEqual(private.status, Lead.Status.NEW)

    def test_lead_actions_validate_log_and_enforce_ownership(self):
        user, profile = self.make_photographer(True, email="actions@example.com", slug="actions")
        _, other = self.make_photographer(True, email="other-actions@example.com", slug="other-actions")
        lead = Lead.objects.create(photographer=profile, first_name="Action", email="action@example.com")
        private = Lead.objects.create(photographer=other, first_name="Private", email="private@example.com")
        self.client.force_login(user)

        self.assertEqual(self.client.post(reverse("photographer_workspace:add_lead_note", args=[private.pk]), {"note": "No access"}).status_code, 404)
        self.client.post(reverse("photographer_workspace:add_lead_note", args=[lead.pk]), {"note": "Prefers afternoons"})
        self.client.post(reverse("photographer_workspace:create_lead_follow_up", args=[lead.pk]), {"title": "Call lead", "due_date": "2026-08-01", "priority": "high"})
        self.client.post(reverse("photographer_workspace:mark_lead_lost", args=[lead.pk]), {"reason": ""})
        lead.refresh_from_db()
        self.assertEqual(lead.status, Lead.Status.NEW)
        self.assertIn("Prefers afternoons", lead.notes)
        self.assertEqual(lead.tasks.get().title, "Call lead")
        self.assertTrue(ClientActivity.objects.filter(lead=lead, event_type=ClientActivity.EventType.NOTE_ADDED).exists())
        self.assertTrue(ClientActivity.objects.filter(lead=lead, event_type=ClientActivity.EventType.FOLLOW_UP_CREATED).exists())

        self.client.post(reverse("photographer_workspace:mark_lead_lost", args=[lead.pk]), {"reason": "Budget changed"})
        lead.refresh_from_db()
        self.assertEqual((lead.status, lead.lost_reason), (Lead.Status.LOST, "Budget changed"))
        self.client.post(reverse("photographer_workspace:archive_lead", args=[lead.pk]))
        lead.refresh_from_db()
        self.assertIsNotNone(lead.archived_at)
        self.assertNotContains(self.client.get(reverse("photographer_workspace:leads")), "action@example.com")

    def test_lead_mutations_require_csrf(self):
        user, profile = self.make_photographer(True, email="csrf@example.com", slug="csrf")
        lead = Lead.objects.create(photographer=profile, first_name="Protected", email="protected@example.com")
        csrf_client = TestClient(enforce_csrf_checks=True)
        csrf_client.force_login(user)
        response = csrf_client.post(reverse("photographer_workspace:mark_lead_booked", args=[lead.pk]))
        self.assertEqual(response.status_code, 403)
        lead.refresh_from_db()
        self.assertEqual(lead.status, Lead.Status.NEW)

class DashboardInformationArchitectureTests(TestCase):
    def make_studio(self, email, slug):
        user = make_user(email)
        studio = PhotographerProfile.objects.create(user=user, slug=slug, onboarding_completed=True, default_currency="USD")
        return user, studio

    def test_dashboard_aggregates_are_real_and_workspace_isolated(self):
        owner, studio = self.make_studio("dashboard-owner@example.com", "dashboard-owner")
        other_owner, other = self.make_studio("dashboard-other@example.com", "dashboard-other")
        client = Client.objects.create(photographer=studio, first_name="Visible", last_name="Client")
        private_client = Client.objects.create(photographer=other, first_name="Private", last_name="Client")
        now = timezone.now()
        booking = ClientSession.objects.create(photographer=studio, client=client, session_type="Portrait", starts_at=now + timedelta(hours=2), status=ClientSession.Status.CONFIRMED)
        ClientSession.objects.create(photographer=other, client=private_client, session_type="Secret shoot", starts_at=now + timedelta(hours=2), status=ClientSession.Status.CONFIRMED)
        invoice = ClientInvoice.objects.create(photographer=studio, client=client, invoice_number="DASH-1", total=Decimal("500"), amount_paid=Decimal("200"), status=ClientInvoice.Status.PARTIALLY_PAID, due_date=timezone.localdate() - timedelta(days=1))
        InvoicePayment.objects.create(photographer=studio, invoice=invoice, amount=Decimal("200"), status=InvoicePayment.Status.COMPLETED)
        other_invoice = ClientInvoice.objects.create(photographer=other, client=private_client, invoice_number="PRIVATE-1", total=Decimal("9000"), status=ClientInvoice.Status.SENT)
        InvoicePayment.objects.create(photographer=other, invoice=other_invoice, amount=Decimal("9000"), status=InvoicePayment.Status.COMPLETED)
        Gallery.objects.create(photographer=studio, client=client, name="Portrait proofs", slug="portrait-proofs", status=Gallery.Status.REVIEW, storage_used=2048)
        Gallery.objects.create(photographer=other, client=private_client, name="Private gallery", slug="private-gallery", status=Gallery.Status.REVIEW)

        self.client.force_login(owner)
        response = self.client.get(reverse("photographer_workspace:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "USD 200.00")
        self.assertContains(response, "USD 300.00")
        self.assertContains(response, "Portrait proofs")
        self.assertContains(response, "Visible Client")
        self.assertContains(response, reverse("photographer_workspace:booking_detail", args=[booking.pk]))
        self.assertNotContains(response, "9000")
        self.assertNotContains(response, "Private gallery")
        self.assertNotContains(response, "Secret shoot")
        self.assertContains(response, "Due date and progress not tracked")

    def test_dashboard_hides_financial_data_from_assigned_photographer(self):
        owner, studio = self.make_studio("studio-owner@example.com", "member-dashboard")
        member_user = make_user("member@example.com")
        membership = StudioMembership.objects.create(studio=studio, user=member_user, role=StudioMembership.Role.PHOTOGRAPHER, status=StudioMembership.Status.ACTIVE)
        client = Client.objects.create(photographer=studio, first_name="Assigned", last_name="Client")
        client.assigned_members.add(membership)
        booking = ClientSession.objects.create(photographer=studio, client=client, session_type="Assigned session", starts_at=timezone.now() + timedelta(days=1))
        booking.assigned_members.add(membership)
        unassigned = ClientSession.objects.create(photographer=studio, client=client, session_type="Owner secret session", starts_at=timezone.now() + timedelta(days=2))
        invoice = ClientInvoice.objects.create(photographer=studio, client=client, invoice_number="SECRET", total=Decimal("7777"), status=ClientInvoice.Status.SENT)
        InvoicePayment.objects.create(photographer=studio, invoice=invoice, amount=Decimal("7777"), status=InvoicePayment.Status.COMPLETED)

        self.client.force_login(member_user)
        response = self.client.get(reverse("photographer_workspace:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Assigned session")
        self.assertNotContains(response, "Owner secret session")
        self.assertNotContains(response, "7777")
        self.assertContains(response, "Financial access is required")
        self.assertNotContains(response, "Send Invoice")

    def test_new_account_has_prioritized_empty_state_without_fake_metrics(self):
        owner, studio = self.make_studio("new-dashboard@example.com", "new-dashboard")
        self.client.force_login(owner)
        response = self.client.get(reverse("photographer_workspace:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add your first client")
        self.assertContains(response, "No performance history yet")
        self.assertNotContains(response, "Needs attention")
        self.assertNotContains(response, "% from last month")
        self.assertNotContains(response, "Business key performance indicators")
        self.assertEqual(response.content.count(b"<h1"), 1)

    def test_dashboard_aggregation_failure_is_safe_and_retryable(self):
        owner, _ = self.make_studio("dashboard-error@example.com", "dashboard-error")
        self.client.force_login(owner)
        with patch("apps.dashboard.views.build_dashboard", side_effect=DatabaseError("private database detail")):
            response = self.client.get(reverse("photographer_workspace:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard data could not be loaded")
        self.assertContains(response, "Retry")
        self.assertNotContains(response, "private database detail")
        self.assertNotContains(response, "Gallery storage")

    def test_dashboard_query_count_is_bounded_as_history_grows(self):
        owner, studio = self.make_studio("dashboard-query@example.com", "dashboard-query")
        client = Client.objects.create(photographer=studio, first_name="Query", last_name="Client")
        for day in range(12):
            ClientSession.objects.create(photographer=studio, client=client, session_type="Portrait", starts_at=timezone.now() + timedelta(days=day + 1))
        self.client.force_login(owner)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("photographer_workspace:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 35)
        self.assertContains(response, "Query Client", count=5)
