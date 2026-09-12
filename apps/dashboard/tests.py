from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientInvoice, ClientSession, InvoicePayment, Lead
from apps.dashboard.analytics_overview import _short_date
from apps.dashboard.team_summary import authorized_studio, parse_team_filters, sessions_overlap
from apps.galleries.models import Gallery, GalleryAnalyticsEvent


def make_user(email, role=User.PrimaryRole.PHOTOGRAPHER):
    return User.objects.create_user(
        email=email,
        password="pass12345",
        primary_role=role,
        last_active_workspace=(
            User.Workspace.PHOTOGRAPHER
            if role == User.PrimaryRole.PHOTOGRAPHER
            else User.Workspace.CLIENT
        ),
        email_verified=True,
        account_status=User.AccountStatus.ACTIVE,
    )


class PhotographerWorkspaceBehaviorTests(TestCase):
    """Behavioral contracts for the photographer workspace.

    These tests intentionally avoid marketing copy, headings, CSS class counts, and
    exact serialized HTML. They protect routes, ownership boundaries, persistence,
    filtering, calculations/exports, and semantic interaction hooks.
    """

    def make_photographer(self, email="photo@example.com", slug="photo", **kwargs):
        user = make_user(email)
        profile = PhotographerProfile.objects.create(
            user=user,
            slug=slug,
            onboarding_completed=True,
            default_currency="USD",
            **kwargs,
        )
        return user, profile

    def test_core_workspace_routes_render_for_completed_photographer(self):
        user, _ = self.make_photographer()
        self.client.force_login(user)
        routes = (
            "dashboard",
            "galleries",
            "all_galleries",
            "clients",
            "crm",
            "leads",
            "bookings",
            "schedule",
            "financial_overview",
            "transactions",
            "growth",
            "analytics",
            "team_overview",
            "team_members",
            "team_performance",
            "settings",
        )
        for name in routes:
            with self.subTest(name=name):
                response = self.client.get(reverse(f"photographer_workspace:{name}"))
                self.assertEqual(response.status_code, 200)

    def test_workspace_routes_require_authentication(self):
        for name in ("dashboard", "analytics", "bookings", "financial_overview", "galleries"):
            with self.subTest(name=name):
                response = self.client.get(reverse(f"photographer_workspace:{name}"))
                self.assertEqual(response.status_code, 302)

    def test_dashboard_isolates_records_by_photographer(self):
        owner, studio = self.make_photographer("owner@example.com", "owner")
        _, other = self.make_photographer("other@example.com", "other")
        owner_client = Client.objects.create(photographer=studio, first_name="Visible", last_name="Client")
        other_client = Client.objects.create(photographer=other, first_name="Private", last_name="Client")
        Gallery.objects.create(
            photographer=studio,
            client=owner_client,
            name="Visible gallery",
            slug="visible-gallery",
            status=Gallery.Status.REVIEW,
        )
        Gallery.objects.create(
            photographer=other,
            client=other_client,
            name="Private gallery",
            slug="private-gallery",
            status=Gallery.Status.REVIEW,
        )
        self.client.force_login(owner)

        response = self.client.get(reverse("photographer_workspace:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible gallery")
        self.assertNotContains(response, "Private gallery")

    def test_bookings_are_owner_scoped_and_detail_route_is_exposed(self):
        owner, studio = self.make_photographer("bookings-owner@example.com", "bookings-owner")
        _, other = self.make_photographer("bookings-other@example.com", "bookings-other")
        client = Client.objects.create(photographer=studio, first_name="Visible", last_name="Booking")
        private_client = Client.objects.create(photographer=other, first_name="Private", last_name="Booking")
        session = ClientSession.objects.create(
            photographer=studio,
            client=client,
            session_type="Visible portrait",
            starts_at=timezone.now() + timedelta(days=1),
            status=ClientSession.Status.CONFIRMED,
        )
        ClientSession.objects.create(
            photographer=other,
            client=private_client,
            session_type="Private portrait",
            starts_at=timezone.now() + timedelta(days=1),
            status=ClientSession.Status.CONFIRMED,
        )
        self.client.force_login(owner)

        response = self.client.get(reverse("photographer_workspace:bookings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible portrait")
        self.assertContains(response, reverse("photographer_workspace:booking_detail", args=[session.pk]))
        self.assertNotContains(response, "Private portrait")

    def test_leads_are_owner_scoped(self):
        owner, studio = self.make_photographer("leads-owner@example.com", "leads-owner")
        _, other = self.make_photographer("leads-other@example.com", "leads-other")
        Lead.objects.create(
            photographer=studio,
            first_name="Visible",
            last_name="Lead",
            estimated_value=Decimal("2400"),
        )
        Lead.objects.create(
            photographer=other,
            first_name="Private",
            last_name="Lead",
            estimated_value=Decimal("9900"),
        )
        self.client.force_login(owner)

        response = self.client.get(reverse("photographer_workspace:leads"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible Lead")
        self.assertNotContains(response, "Private Lead")
        self.assertNotContains(response, "9900")

    def test_financial_pages_are_owner_scoped(self):
        owner, studio = self.make_photographer("finance-owner@example.com", "finance-owner")
        _, other = self.make_photographer("finance-other@example.com", "finance-other")
        client = Client.objects.create(photographer=studio, first_name="Visible", last_name="Client")
        private_client = Client.objects.create(photographer=other, first_name="Private", last_name="Client")
        invoice = ClientInvoice.objects.create(
            photographer=studio,
            client=client,
            invoice_number="VISIBLE-INV",
            total=Decimal("500"),
        )
        InvoicePayment.objects.create(
            photographer=studio,
            invoice=invoice,
            amount=Decimal("200"),
            status=InvoicePayment.Status.COMPLETED,
        )
        private_invoice = ClientInvoice.objects.create(
            photographer=other,
            client=private_client,
            invoice_number="PRIVATE-INV",
            total=Decimal("9000"),
        )
        InvoicePayment.objects.create(
            photographer=other,
            invoice=private_invoice,
            amount=Decimal("9000"),
            status=InvoicePayment.Status.COMPLETED,
        )
        self.client.force_login(owner)

        for route in ("financial_overview", "transactions"):
            with self.subTest(route=route):
                response = self.client.get(reverse(f"photographer_workspace:{route}"))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "PRIVATE-INV")
                self.assertNotContains(response, "9000")

    def test_gallery_pages_are_owner_scoped(self):
        owner, studio = self.make_photographer("gallery-owner@example.com", "gallery-owner")
        _, other = self.make_photographer("gallery-other@example.com", "gallery-other")
        client = Client.objects.create(photographer=studio, first_name="Visible", last_name="Client")
        private_client = Client.objects.create(photographer=other, first_name="Private", last_name="Client")
        gallery = Gallery.objects.create(
            photographer=studio,
            client=client,
            name="Visible gallery",
            slug="visible-owner-gallery",
            status=Gallery.Status.REVIEW,
        )
        private_gallery = Gallery.objects.create(
            photographer=other,
            client=private_client,
            name="Private gallery",
            slug="private-owner-gallery",
            status=Gallery.Status.REVIEW,
        )
        self.client.force_login(owner)

        dashboard = self.client.get(reverse("photographer_workspace:galleries"))
        workspace = self.client.get(reverse("photographer_workspace:gallery_workspace", args=[gallery.pk]))
        forbidden = self.client.get(reverse("photographer_workspace:gallery_workspace", args=[private_gallery.pk]))

        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "Visible gallery")
        self.assertNotContains(dashboard, "Private gallery")
        self.assertEqual(workspace.status_code, 200)
        self.assertEqual(forbidden.status_code, 404)

    def test_gallery_workspace_exposes_semantic_action_routes(self):
        owner, studio = self.make_photographer("gallery-actions@example.com", "gallery-actions")
        client = Client.objects.create(photographer=studio, first_name="Client", last_name="One")
        gallery = Gallery.objects.create(
            photographer=studio,
            client=client,
            name="Action gallery",
            slug="action-gallery",
            status=Gallery.Status.REVIEW,
        )
        self.client.force_login(owner)

        response = self.client.get(reverse("photographer_workspace:gallery_workspace", args=[gallery.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("photographer_workspace:gallery_preview", args=[gallery.pk]))
        self.assertContains(response, "?tab=client-access")
        self.assertContains(response, "?tab=photos")

    def test_analytics_filters_are_preserved_semantically(self):
        owner, studio = self.make_photographer("analytics-filter@example.com", "analytics-filter")
        client = Client.objects.create(photographer=studio, first_name="Filter", last_name="Client")
        ClientSession.objects.create(
            photographer=studio,
            client=client,
            session_type="Portrait",
            location="Studio A",
            starts_at=timezone.now(),
            status=ClientSession.Status.CONFIRMED,
        )
        self.client.force_login(owner)

        response = self.client.get(
            reverse("photographer_workspace:analytics"),
            {"range": "this_quarter", "compare": "previous_year", "location": "Studio A", "service": "Portrait"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-analytics-form')
        self.assertContains(response, 'value="this_quarter" selected')
        self.assertContains(response, 'value="previous_year" selected')
        self.assertContains(response, 'data-remove-filter="location"')
        self.assertContains(response, 'data-remove-filter="service"')

    def test_analytics_exposes_stable_component_and_accessibility_hooks(self):
        owner, _ = self.make_photographer("analytics-hooks@example.com", "analytics-hooks")
        self.client.force_login(owner)

        response = self.client.get(reverse("photographer_workspace:analytics"))

        self.assertEqual(response.status_code, 200)
        for hook in (
            'data-business-performance',
            'data-trend-card',
            'data-trend-plot',
            'data-metric-dialog',
            'data-metric-open',
            'aria-haspopup="dialog"',
            'data-print-report',
        ):
            self.assertContains(response, hook)

    def test_analytics_uses_only_owner_records(self):
        owner, studio = self.make_photographer("analytics-owner@example.com", "analytics-owner")
        _, other = self.make_photographer("analytics-other@example.com", "analytics-other")
        client = Client.objects.create(photographer=studio, first_name="Owner", last_name="Client")
        other_client = Client.objects.create(photographer=other, first_name="Other", last_name="Client")
        booking = ClientSession.objects.create(
            photographer=studio,
            client=client,
            session_type="Portrait",
            starts_at=timezone.now(),
            status=ClientSession.Status.CONFIRMED,
            booking_value=Decimal("1200"),
        )
        other_booking = ClientSession.objects.create(
            photographer=other,
            client=other_client,
            session_type="Secret",
            starts_at=timezone.now(),
            status=ClientSession.Status.CONFIRMED,
            booking_value=Decimal("9000"),
        )
        invoice = ClientInvoice.objects.create(photographer=studio, client=client, booking=booking, total=Decimal("1200"))
        private_invoice = ClientInvoice.objects.create(photographer=other, client=other_client, booking=other_booking, total=Decimal("9000"))
        InvoicePayment.objects.create(photographer=studio, invoice=invoice, amount=Decimal("1200"), processor_fee=Decimal("36"), status=InvoicePayment.Status.COMPLETED)
        InvoicePayment.objects.create(photographer=other, invoice=private_invoice, amount=Decimal("9000"), status=InvoicePayment.Status.COMPLETED)
        gallery = Gallery.objects.create(photographer=studio, client=client, name="Owner gallery", slug="owner-gallery", status=Gallery.Status.PUBLISHED)
        private_gallery = Gallery.objects.create(photographer=other, client=other_client, name="Private gallery", slug="private-analytics-gallery", status=Gallery.Status.PUBLISHED)
        GalleryAnalyticsEvent.objects.create(photographer=studio, gallery=gallery, event_type=GalleryAnalyticsEvent.EventType.VIEW, visitor_identifier="owner-visitor")
        GalleryAnalyticsEvent.objects.create(photographer=other, gallery=private_gallery, event_type=GalleryAnalyticsEvent.EventType.VIEW, visitor_identifier="private-visitor")
        self.client.force_login(owner)

        response = self.client.get(reverse("photographer_workspace:analytics"), {"range": "30_days", "compare": "none"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-value="$1,200"')
        self.assertContains(response, 'data-value="$1,164"')
        self.assertNotContains(response, "$9,000")

    def test_analytics_csv_export_is_available(self):
        owner, _ = self.make_photographer("analytics-export@example.com", "analytics-export")
        self.client.force_login(owner)

        response = self.client.get(reverse("photographer_workspace:analytics"), {"export": "csv"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))

    def test_client_detail_is_owner_scoped(self):
        owner, studio = self.make_photographer("client-owner@example.com", "client-owner")
        _, other = self.make_photographer("client-other@example.com", "client-other")
        client = Client.objects.create(photographer=studio, first_name="Visible", last_name="Client")
        private_client = Client.objects.create(photographer=other, first_name="Private", last_name="Client")
        self.client.force_login(owner)

        own = self.client.get(reverse("photographer_workspace:client_detail", args=[client.pk]))
        forbidden = self.client.get(reverse("photographer_workspace:client_detail", args=[private_client.pk]))

        self.assertEqual(own.status_code, 200)
        self.assertEqual(forbidden.status_code, 404)

    def test_team_authorization_and_filter_allow_lists(self):
        user, profile = self.make_photographer("authorized@example.com", "authorized")
        self.assertEqual(authorized_studio(user), profile)
        outsider = make_user("client-only@example.com", User.PrimaryRole.CLIENT)
        with self.assertRaises(PermissionDenied):
            authorized_studio(outsider)

        filters = parse_team_filters(
            {
                "date": "not-a-date",
                "location": "x" * 300,
                "role": "administrator",
                "availability": "invented",
            }
        )
        self.assertEqual(filters["date"], timezone.localdate())
        self.assertEqual(len(filters["location"]), 255)
        self.assertEqual(filters["role"], "")
        self.assertEqual(filters["availability"], "")

    def test_session_overlap_uses_duration_and_ignores_same_record(self):
        owner, studio = self.make_photographer("overlap@example.com", "overlap")
        client = Client.objects.create(photographer=studio, first_name="Schedule", last_name="Client")
        starts = timezone.make_aware(datetime.combine(timezone.localdate(), time(9)))
        first = ClientSession.objects.create(
            photographer=studio,
            client=client,
            session_type="First",
            starts_at=starts,
            duration_minutes=60,
        )
        overlapping = ClientSession.objects.create(
            photographer=studio,
            client=client,
            session_type="Second",
            starts_at=starts + timedelta(minutes=30),
            duration_minutes=60,
        )

        self.assertFalse(sessions_overlap(first, first))
        self.assertTrue(sessions_overlap(first, overlapping))

    def test_short_date_is_stable_for_analytics_serialization(self):
        self.assertEqual(_short_date(datetime(2026, 9, 12, 10, 30)), "Sep 12")
