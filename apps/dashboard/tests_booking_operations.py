from datetime import datetime, timedelta

from django.contrib import admin
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.admin import ClientActivityAdmin
from apps.clients.models import Client, ClientActivity, ClientSession
from apps.dashboard.models import StudioMembership


class BookingOperationsAuditTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="booking-a@example.com", password="pass12345",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            last_active_workspace=User.Workspace.PHOTOGRAPHER,
            email_verified=True, account_status=User.AccountStatus.ACTIVE,
        )
        self.studio = PhotographerProfile.objects.create(
            user=self.user, slug="booking-a", onboarding_completed=True,
        )
        self.client_record = Client.objects.create(
            photographer=self.studio, first_name="Avery", last_name="O'Neil",
            email="avery@example.test",
        )
        self.url = reverse("photographer_workspace:schedule")
        self.client.force_login(self.user)
        self.start = timezone.make_aware(datetime(2026, 8, 12, 10))

    def make_booking(self, *, client=None, offset=0, **values):
        defaults = {
            "photographer": self.studio,
            "client": client or self.client_record,
            "session_type": "Family Portrait",
            "starts_at": self.start + timedelta(hours=offset),
            "duration_minutes": 60,
            "location": "North Studio",
            "status": ClientSession.Status.CONFIRMED,
        }
        defaults.update(values)
        return ClientSession.objects.create(**defaults)

    def get_events(self, **params):
        response = self.client.get(self.url, {
            "view": "list", "date": "2026-08-01", **params,
        })
        self.assertEqual(response.status_code, 200)
        return response, response.context["schedule_events"]

    def test_search_exact_partial_case_whitespace_booking_number_and_special_characters(self):
        booking = self.make_booking()
        for term in ("Avery", "ave", "AVERY", "  Avery  ", "Portrait", "north", f"LP-{booking.pk:04d}", str(booking.pk), "O'Neil"):
            with self.subTest(term=term):
                _, events = self.get_events(q=term)
                self.assertEqual([event["id"] for event in events], [booking.pk])
        _, events = self.get_events(q="avery@example.test")
        self.assertEqual(events, [], "Email is not advertised as a schedule search field.")
        _, events = self.get_events(q="%_[]")
        self.assertEqual(events, [])

    def test_search_and_existing_filters_combine_and_invalid_values_are_safe(self):
        matching = self.make_booking()
        self.make_booking(offset=2, session_type="Wedding", location="Garden")
        _, events = self.get_events(q="avery", session_type="Family Portrait",
                                    location="North Studio", status="confirmed",
                                    event_type="booking")
        self.assertEqual([event["id"] for event in events], [matching.pk])
        for params in ({"status": "bogus"}, {"event_type": "bogus"},
                       {"member": "not-an-id"}, {"scope": "bogus"}):
            with self.subTest(params=params):
                _, events = self.get_events(**params)
                self.assertEqual(events, [])
        _, events = self.get_events(q="avery")
        self.assertEqual(len(events), 2)

    def test_member_scope_and_foreign_related_id_do_not_leak(self):
        member_user = User.objects.create_user(
            email="member@example.com", password="pass12345",
            primary_role=User.PrimaryRole.PHOTOGRAPHER, email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        member = StudioMembership.objects.create(
            studio=self.studio, user=member_user,
            role=StudioMembership.Role.PHOTOGRAPHER,
            status=StudioMembership.Status.ACTIVE,
        )
        assigned = self.make_booking()
        assigned.assigned_members.add(member)
        unassigned = self.make_booking(offset=2)

        _, events = self.get_events(member=str(member.pk))
        self.assertEqual([event["id"] for event in events], [assigned.pk])
        _, events = self.get_events(scope="me")
        self.assertEqual([event["id"] for event in events], [unassigned.pk])

        other_user = User.objects.create_user(
            email="booking-b@example.com", password="pass12345",
            primary_role=User.PrimaryRole.PHOTOGRAPHER, email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        other = PhotographerProfile.objects.create(
            user=other_user, slug="booking-b", onboarding_completed=True,
        )
        foreign_member = StudioMembership.objects.create(
            studio=other, user=other_user, role=StudioMembership.Role.PHOTOGRAPHER,
            status=StudioMembership.Status.ACTIVE,
        )
        private_client = Client.objects.create(photographer=other, first_name="Private")
        private_booking = ClientSession.objects.create(
            photographer=other, client=private_client, session_type="Secret",
            starts_at=self.start, status=ClientSession.Status.CONFIRMED,
        )
        _, events = self.get_events(member=str(foreign_member.pk))
        self.assertEqual(events, [])
        _, events = self.get_events(q="Private")
        self.assertNotIn(private_booking.pk, [event["id"] for event in events])

    def test_pagination_count_order_and_query_persistence(self):
        bookings = [self.make_booking(offset=index) for index in range(12)]
        first, _ = self.get_events(q="Avery", status="confirmed", sort="date")
        second, _ = self.get_events(q="Avery", status="confirmed", sort="date", page="2")
        self.assertEqual(first.context["booking_page"].paginator.count, 12)
        self.assertEqual(len(first.context["booking_page"].object_list), 10)
        self.assertEqual(len(second.context["booking_page"].object_list), 2)
        self.assertEqual(first.context["booking_page"][0]["id"], bookings[0].pk)
        self.assertEqual(second.context["booking_page"][0]["id"], bookings[10].pk)
        self.assertIn("q=Avery", first.context["list_query"])
        self.assertIn("status=confirmed", first.context["list_query"])

    def test_create_edit_reschedule_cancel_activity_is_scoped_and_deduplicated(self):
        create_payload = {
            "action": "create_booking", "client": self.client_record.pk,
            "session_type": "Portrait", "start_date": "2026-08-12",
            "start_time": "10:00", "end_date": "2026-08-12",
            "end_time": "11:00", "booking_status": "confirmed",
        }
        response = self.client.post(reverse("photographer_workspace:bookings"), create_payload)
        self.assertEqual(response.status_code, 201)
        booking = ClientSession.objects.get()
        created = booking.activities.get(event_type=ClientActivity.EventType.BOOKING_CREATED)
        self.assertEqual((created.actor, created.client, created.photographer),
                         (self.user, self.client_record, self.studio))

        edit_payload = create_payload | {"action": "edit_booking", "booking_id": booking.pk,
                                         "start_time": "12:00", "end_time": "13:00"}
        self.assertEqual(self.client.post(reverse("photographer_workspace:bookings"), edit_payload).status_code, 200)
        audit = booking.activities.get(event_type=ClientActivity.EventType.BOOKING_RESCHEDULED)
        self.assertIn("starts_at", audit.metadata["changes"])
        self.assertIn("before", audit.metadata["changes"]["starts_at"])
        self.assertIn("after", audit.metadata["changes"]["starts_at"])
        self.client.post(reverse("photographer_workspace:bookings"), edit_payload)
        self.assertEqual(booking.activities.filter(event_type=ClientActivity.EventType.BOOKING_RESCHEDULED).count(), 1)
        self.assertFalse(booking.activities.filter(event_type=ClientActivity.EventType.BOOKING_UPDATED).exists(),
                         list(booking.activities.values_list("event_type", "metadata")))

        action_url = reverse("photographer_workspace:booking_action", args=[booking.pk])
        self.client.post(action_url, {"action": "cancel", "reason": "Client request"})
        self.client.post(action_url, {"action": "cancel", "reason": "again"})
        cancelled = booking.activities.get(event_type=ClientActivity.EventType.BOOKING_CANCELLED)
        self.assertEqual(cancelled.metadata, {"reason": "Client request"})
        self.assertEqual(booking.activities.filter(event_type=ClientActivity.EventType.BOOKING_CANCELLED).count(), 1)
        self.assertEqual(list(booking.activities.values_list("event_type", flat=True)), [
            ClientActivity.EventType.BOOKING_CANCELLED,
            ClientActivity.EventType.BOOKING_RESCHEDULED,
            ClientActivity.EventType.BOOKING_CREATED,
        ])

    def test_activity_isolation_consultation_event_and_admin_audit_immutability(self):
        consultation_payload = {
            "action": "create_consultation", "contact": self.client_record.pk,
            "meeting_type": "Discovery", "start_date": "2026-08-12",
            "start_time": "10:00", "end_date": "2026-08-12", "end_time": "11:00",
            "booking_status": "tentative",
        }
        self.client.post(reverse("photographer_workspace:bookings"), consultation_payload)
        activity = ClientActivity.objects.get()
        self.assertEqual(activity.event_type, ClientActivity.EventType.CONSULTATION_SCHEDULED)
        detail = self.client.get(reverse("photographer_workspace:booking_detail", args=[activity.booking_id]))
        self.assertContains(detail, "Consultation scheduled")

        admin_view = ClientActivityAdmin(ClientActivity, admin.site)
        request = RequestFactory().get("/admin/")
        request.user = self.user
        self.assertFalse(admin_view.has_add_permission(request))
        self.assertFalse(admin_view.has_delete_permission(request, activity))
        self.assertEqual(set(admin_view.get_readonly_fields(request, activity)),
                         {field.name for field in ClientActivity._meta.fields})
