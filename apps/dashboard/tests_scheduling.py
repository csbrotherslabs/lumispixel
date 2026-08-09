from datetime import datetime, time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientSession
from apps.dashboard.models import StudioMembership
from apps.dashboard.scheduling import availability_for


class SchedulingIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="schedule-a@example.com", password="pass12345",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            last_active_workspace=User.Workspace.PHOTOGRAPHER,
            email_verified=True, account_status=User.AccountStatus.ACTIVE,
        )
        self.studio = PhotographerProfile.objects.create(
            user=self.user, slug="schedule-a", onboarding_completed=True,
            timezone="America/New_York",
        )
        self.client_record = Client.objects.create(
            photographer=self.studio, first_name="Avery", last_name="Stone"
        )
        self.client.force_login(self.user)
        self.url = reverse("photographer_workspace:bookings")

    def payload(self, start="10:00", end="11:00", **values):
        payload = {
            "action": "create_booking", "client": self.client_record.pk,
            "session_type": "Portrait", "start_date": "2026-08-12",
            "start_time": start, "end_date": "2026-08-12", "end_time": end,
            "location": "Studio A", "booking_status": "confirmed", "price": "100",
        }
        payload.update(values)
        return payload

    def create_member(self, email):
        user = User.objects.create_user(
            email=email, password="pass12345", primary_role=User.PrimaryRole.PHOTOGRAPHER,
            email_verified=True, account_status=User.AccountStatus.ACTIVE,
        )
        return StudioMembership.objects.create(
            studio=self.studio, user=user, role=StudioMembership.Role.PHOTOGRAPHER,
            status=StudioMembership.Status.ACTIVE, working_days=["Wed"],
            working_hours_start=time(9), working_hours_end=time(17),
            time_zone="America/New_York",
        )

    def test_booking_is_source_for_every_calendar_view_and_edit_propagates(self):
        created = self.client.post(self.url, self.payload(end="11:30"))
        self.assertEqual(created.status_code, 201)
        booking = ClientSession.objects.get(photographer=self.studio)
        for view in ("month", "week", "day", "agenda", "list"):
            page = self.client.get(reverse("photographer_workspace:schedule"), {
                "view": view, "date": "2026-08-12",
            })
            self.assertContains(page, "Avery Stone")
            self.assertContains(page, "Studio A")
            self.assertContains(page, "Confirmed")

        edited = self.client.post(self.url, self.payload(
            action="edit_booking", booking_id=booking.pk, start="13:00", end="14:15",
            location="Garden",
        ))
        self.assertEqual(edited.status_code, 200)
        booking.refresh_from_db()
        self.assertEqual(timezone.localtime(booking.starts_at).strftime("%H:%M"), "13:00")
        self.assertEqual(booking.duration_minutes, 75)
        page = self.client.get(reverse("photographer_workspace:schedule"), {
            "view": "agenda", "date": "2026-08-12",
        })
        self.assertContains(page, "1:00 PM")
        self.assertContains(page, "2:15 PM")
        self.assertContains(page, "Garden")

        cancel = self.client.post(reverse("photographer_workspace:booking_action", args=[booking.pk]), {"action": "cancel"})
        self.assertEqual(cancel.status_code, 302)
        active = self.client.get(reverse("photographer_workspace:schedule"), {"view": "agenda", "date": "2026-08-12"})
        self.assertEqual(active.context["schedule_events"], [])
        cancelled = self.client.get(reverse("photographer_workspace:schedule"), {
            "view": "agenda", "date": "2026-08-12", "show_cancelled": "1",
        })
        self.assertContains(cancelled, "Cancelled")

    def test_create_rejects_all_overlap_shapes_but_allows_adjacent(self):
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 201)
        for start, end in (("10:30", "11:30"), ("09:30", "10:30"), ("10:00", "11:00")):
            response = self.client.post(self.url, self.payload(start, end))
            self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.post(self.url, self.payload("11:00", "12:00")).status_code, 201)
        self.assertEqual(ClientSession.objects.for_photographer(self.studio).count(), 2)

    def test_distinct_photographers_can_book_simultaneously_and_hours_apply(self):
        member_a = self.create_member("member-a@example.com")
        member_b = self.create_member("member-b@example.com")
        self.assertEqual(self.client.post(self.url, self.payload(team=[member_a.pk])).status_code, 201)
        self.assertEqual(self.client.post(self.url, self.payload(team=[member_b.pk])).status_code, 201)
        same_member = self.client.post(self.url, self.payload(team=[member_a.pk]))
        self.assertEqual(same_member.status_code, 409)
        outside_hours = self.client.post(self.url, self.payload("18:00", "19:00", team=[member_b.pk]))
        self.assertEqual(outside_hours.status_code, 409)

    def test_reschedule_collision_uses_the_same_rule(self):
        first = self.client.post(self.url, self.payload("10:00", "11:00"))
        second = self.client.post(self.url, self.payload("12:00", "13:00"))
        self.assertEqual((first.status_code, second.status_code), (201, 201))
        moving = ClientSession.objects.for_photographer(self.studio).latest("pk")
        start = timezone.make_aware(datetime(2026, 8, 12, 10, 30), timezone.get_current_timezone())
        response = self.client.post(
            reverse("photographer_workspace:reschedule_session", args=[moving.pk]),
            data={"starts_at": start.isoformat(), "duration_minutes": 60, "preview": False},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)

    def test_calendar_and_availability_are_tenant_scoped(self):
        other_user = User.objects.create_user(
            email="schedule-b@example.com", password="pass12345",
            primary_role=User.PrimaryRole.PHOTOGRAPHER, email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        other = PhotographerProfile.objects.create(user=other_user, slug="schedule-b", onboarding_completed=True)
        private_client = Client.objects.create(photographer=other, first_name="Private", last_name="Client")
        start = timezone.make_aware(datetime(2026, 8, 12, 10), timezone.get_current_timezone())
        private = ClientSession.objects.create(photographer=other, client=private_client, session_type="Private", starts_at=start)

        page = self.client.get(reverse("photographer_workspace:schedule"), {"view": "day", "date": "2026-08-12"})
        self.assertNotContains(page, "Private Client")
        result = availability_for(studio=self.studio, starts_at=start, duration_minutes=60)
        self.assertTrue(result["available"])
        move = self.client.post(reverse("photographer_workspace:reschedule_session", args=[private.pk]), data={}, content_type="application/json")
        self.assertEqual(move.status_code, 404)
