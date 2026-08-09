from datetime import datetime, time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientSession
from apps.dashboard.models import ScheduleConstraint, StudioMembership
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

    def constraint_payload(self, kind="blocked", **values):
        payload = {
            "action": "create_constraint", "event_type": kind, "title": "Unavailable",
            "reason": "Personal appointment", "start_date": "2026-08-12", "start_time": "10:00",
            "end_date": "2026-08-12", "end_time": "11:00", "prevent_booking": "on",
            "availability_scope": "selected",
        }
        payload.update(values)
        return payload

    def test_block_create_edit_delete_persists_and_recalculates_availability(self):
        created = self.client.post(self.url, self.constraint_payload())
        self.assertEqual(created.status_code, 201)
        block = ScheduleConstraint.objects.get(studio=self.studio)
        self.assertTrue(block.blocks_booking)
        page = self.client.get(reverse("photographer_workspace:schedule"), {"view": "day", "date": "2026-08-12"})
        self.assertContains(page, "Unavailable")
        self.assertEqual(self.client.post(self.url, self.payload("10:30", "10:45")).status_code, 409)
        self.assertEqual(self.client.post(self.url, self.payload("09:00", "10:00")).status_code, 201)
        self.assertEqual(self.client.post(self.url, self.payload("11:00", "12:00")).status_code, 201)

        edited = self.client.post(self.url, self.constraint_payload(
            action="edit_constraint", constraint_id=block.pk, title="Updated block",
            reason="Updated reason", start_time="13:00", end_time="14:00",
        ))
        self.assertEqual(edited.status_code, 200)
        block.refresh_from_db()
        self.assertEqual((block.title, block.reason), ("Updated block", "Updated reason"))
        self.assertEqual(timezone.localtime(block.starts_at).hour, 13)
        removed = self.client.post(reverse("photographer_workspace:constraint_action", args=[block.pk]), {"action": "delete"})
        self.assertEqual(removed.status_code, 302)
        self.assertFalse(ScheduleConstraint.objects.filter(pk=block.pk).exists())
        self.assertEqual(self.client.post(self.url, self.payload("13:00", "14:00")).status_code, 201)

    def test_editing_is_persisted_and_informational(self):
        response = self.client.post(self.url, self.constraint_payload(
            kind="editing", title="Cull gallery", reason="", prevent_booking="",
        ))
        self.assertEqual(response.status_code, 201)
        editing = ScheduleConstraint.objects.get()
        self.assertFalse(editing.blocks_booking)
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 201)

    def test_vacation_supports_single_and_multi_day_and_blocks_reschedule(self):
        response = self.client.post(self.url, self.constraint_payload(
            kind="vacation", title="Summer leave", all_day="on", end_date="2026-08-14",
        ))
        self.assertEqual(response.status_code, 201)
        vacation = ScheduleConstraint.objects.get()
        self.assertEqual((vacation.ends_at - vacation.starts_at).days, 3)
        self.assertEqual(self.client.post(self.url, self.payload(
            start="12:00", end="13:00", start_date="2026-08-13", end_date="2026-08-13",
        )).status_code, 409)
        self.assertEqual(self.client.post(self.url, self.payload(
            start="00:00", end="01:00", start_date="2026-08-15", end_date="2026-08-15",
        )).status_code, 201)

    def test_constraints_are_tenant_scoped_and_member_ids_cannot_be_injected(self):
        other_user = User.objects.create_user(
            email="other-owner@example.com", password="pass12345",
            primary_role=User.PrimaryRole.PHOTOGRAPHER, email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        other = PhotographerProfile.objects.create(user=other_user, slug="other-constraints", onboarding_completed=True)
        foreign_member = StudioMembership.objects.create(
            studio=other, user=other_user, role=StudioMembership.Role.PHOTOGRAPHER,
            status=StudioMembership.Status.ACTIVE,
        )
        injected = self.client.post(self.url, self.constraint_payload(team=[foreign_member.pk]))
        self.assertEqual(injected.status_code, 400)
        foreign = ScheduleConstraint.objects.create(
            studio=other, kind="blocked", title="Private leave", starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(hours=1), blocks_booking=True,
        )
        self.assertEqual(self.client.post(
            reverse("photographer_workspace:constraint_action", args=[foreign.pk]), {"action": "delete"},
        ).status_code, 404)
        self.assertNotContains(self.client.get(
            reverse("photographer_workspace:schedule"), {"date": timezone.localdate().isoformat()},
        ), "Private leave")

    def test_photographer_cannot_modify_other_member_or_entire_team_constraint(self):
        member = self.create_member("restricted@example.com")
        other_member = self.create_member("other-member@example.com")
        self.client.force_login(member.user)
        self.assertEqual(self.client.post(self.url, self.constraint_payload(team=[other_member.pk])).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.constraint_payload(
            team=[member.pk], availability_scope="entire_team",
        )).status_code, 403)
        own = self.client.post(self.url, self.constraint_payload(team=[member.pk]))
        self.assertEqual(own.status_code, 201)
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
