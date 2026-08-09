from datetime import datetime, timedelta

from django.contrib import admin
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.admin import ClientActivityAdmin
from apps.clients.models import Client, ClientActivity, ClientSession
from apps.dashboard.models import ScheduleConstraint, StudioMembership


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

    def test_role_permission_matrix_is_enforced_at_server_endpoints(self):
        """Owners/managers manage the studio; photographers manage assigned resources only."""
        for role in (StudioMembership.Role.MANAGER, StudioMembership.Role.PHOTOGRAPHER):
            with self.subTest(role=role):
                user = User.objects.create_user(
                    email=f"{role}@example.test", password="pass12345",
                    primary_role=User.PrimaryRole.PHOTOGRAPHER, email_verified=True,
                    account_status=User.AccountStatus.ACTIVE,
                )
                member = StudioMembership.objects.create(
                    studio=self.studio, user=user, role=role, status=StudioMembership.Status.ACTIVE,
                )
                assigned_client = Client.objects.create(
                    photographer=self.studio, first_name=role, email=f"client-{role}@example.test",
                )
                assigned_client.assigned_members.add(member)
                booking = self.make_booking(client=assigned_client, offset=4)
                booking.assigned_members.add(member)
                block = ScheduleConstraint.objects.create(
                    studio=self.studio, kind=ScheduleConstraint.Kind.BLOCKED, title="Own block",
                    starts_at=self.start + timedelta(days=1), ends_at=self.start + timedelta(days=1, hours=1),
                    blocks_booking=True, created_by=self.user,
                )
                block.assigned_members.add(member)
                self.client.force_login(user)

                self.assertEqual(self.client.get(reverse("photographer_workspace:schedule")).status_code, 200)
                self.assertEqual(self.client.get(reverse("photographer_workspace:booking_detail", args=[booking.pk])).status_code, 200)
                payload = {
                    "action": "create_booking", "client": assigned_client.pk, "session_type": "Role test",
                    "start_date": "2026-08-14", "start_time": "10:00", "end_date": "2026-08-14",
                    "end_time": "11:00", "booking_status": "confirmed", "team": [member.pk],
                }
                self.assertEqual(self.client.post(reverse("photographer_workspace:bookings"), payload).status_code, 201)
                created = ClientSession.objects.get(session_type="Role test", assigned_members=member)
                self.assertEqual(self.client.post(reverse("photographer_workspace:bookings"), payload | {
                    "action": "edit_booking", "booking_id": created.pk, "start_time": "12:00", "end_time": "13:00",
                }).status_code, 200)
                self.assertEqual(self.client.post(
                    reverse("photographer_workspace:reschedule_session", args=[created.pk]),
                    data='{"starts_at":"2026-08-14T14:00:00Z","duration_minutes":60,"preview":false}',
                    content_type="application/json",
                ).status_code, 200)
                self.assertEqual(self.client.post(
                    reverse("photographer_workspace:booking_action", args=[created.pk]), {"action": "cancel"},
                ).status_code, 302)
                constraint_payload = {
                    "action": "edit_constraint", "constraint_id": block.pk, "event_type": "blocked",
                    "title": "Edited", "reason": "Role check", "start_date": "2026-08-13",
                    "start_time": "10:00", "end_date": "2026-08-13", "end_time": "11:00",
                    "prevent_booking": "on", "availability_scope": "selected", "team": [member.pk],
                }
                self.assertEqual(self.client.post(reverse("photographer_workspace:bookings"), constraint_payload).status_code, 200)
                self.assertEqual(self.client.post(
                    reverse("photographer_workspace:constraint_action", args=[block.pk]), {"action": "delete"},
                ).status_code, 302)

    def test_photographer_booking_without_team_uses_authenticated_membership(self):
        """The shared browser form may omit team; the server supplies the trusted assignment."""
        member_user = User.objects.create_user(
            email="default-assignment@example.test", password="pass12345",
            primary_role=User.PrimaryRole.PHOTOGRAPHER, email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        member = StudioMembership.objects.create(
            studio=self.studio, user=member_user, role=StudioMembership.Role.PHOTOGRAPHER,
            status=StudioMembership.Status.ACTIVE,
        )
        assigned_client = Client.objects.create(
            photographer=self.studio, first_name="Morgan", last_name="Lee",
            email="morgan@example.test",
        )
        assigned_client.assigned_members.add(member)
        self.client.force_login(member_user)

        response = self.client.post(reverse("photographer_workspace:bookings"), {
            "action": "create_booking", "event_type": "booking",
            "client": assigned_client.pk, "title": "Morgan brand portraits",
            "session_type": "Brand portrait", "start_date": "2026-08-12",
            "start_time": "14:00", "end_date": "2026-08-12", "end_time": "15:30",
            "location": "North Studio", "booking_status": "confirmed", "price": "475.00",
            "notes": "Two wardrobe changes.",
        }, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        self.assertEqual(response.status_code, 201)
        booking = ClientSession.objects.get(photographer=self.studio, client=assigned_client)
        self.assertEqual(list(booking.assigned_members.all()), [member])
        self.assertEqual(booking.duration_minutes, 90)
        self.assertEqual(booking.booking_value, 475)
        self.assertEqual(booking.activities.filter(
            event_type=ClientActivity.EventType.BOOKING_CREATED,
        ).count(), 1)
        self.assertEqual(ClientSession.objects.filter(photographer=self.studio).count(), 1)

    def test_photographer_cannot_view_or_mutate_unassigned_booking_or_client(self):
        member_user = User.objects.create_user(
            email="restricted-booker@example.test", password="pass12345",
            primary_role=User.PrimaryRole.PHOTOGRAPHER, email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        member = StudioMembership.objects.create(
            studio=self.studio, user=member_user, role=StudioMembership.Role.PHOTOGRAPHER,
            status=StudioMembership.Status.ACTIVE,
        )
        private_booking = self.make_booking(offset=6)
        self.client.force_login(member_user)
        detail = reverse("photographer_workspace:booking_detail", args=[private_booking.pk])
        action = reverse("photographer_workspace:booking_action", args=[private_booking.pk])
        move = reverse("photographer_workspace:reschedule_session", args=[private_booking.pk])
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.post(action, {"action": "cancel"}).status_code, 404)
        self.assertEqual(self.client.post(move, data="{}", content_type="application/json").status_code, 404)
        response = self.client.post(reverse("photographer_workspace:bookings"), {
            "action": "create_booking", "client": self.client_record.pk, "session_type": "Injected",
            "start_date": "2026-08-15", "start_time": "10:00", "end_date": "2026-08-15",
            "end_time": "11:00", "booking_status": "confirmed", "team": [member.pk],
        })
        self.assertEqual(response.status_code, 400)
        page = self.client.get(self.url, {"view": "list", "date": "2026-08-01", "q": "Avery"})
        self.assertEqual(page.context["schedule_events"], [])
        self.assertNotIn(self.client_record, page.context["booking_clients"])

    def test_cross_workspace_url_form_payload_and_related_id_attacks_fail_closed(self):
        other_user = User.objects.create_user(
            email="attack-b@example.test", password="pass12345",
            primary_role=User.PrimaryRole.PHOTOGRAPHER, email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        other = PhotographerProfile.objects.create(user=other_user, slug="attack-b", onboarding_completed=True)
        foreign_client = Client.objects.create(photographer=other, first_name="TenantSecret")
        foreign_booking = ClientSession.objects.create(
            photographer=other, client=foreign_client, session_type="Secret service",
            starts_at=self.start, status=ClientSession.Status.CONFIRMED,
        )
        foreign_member = StudioMembership.objects.create(
            studio=other, user=other_user, role=StudioMembership.Role.PHOTOGRAPHER,
            status=StudioMembership.Status.ACTIVE,
        )
        foreign_block = ScheduleConstraint.objects.create(
            studio=other, kind=ScheduleConstraint.Kind.VACATION, title="Secret vacation",
            starts_at=self.start, ends_at=self.start + timedelta(hours=1), created_by=other_user,
        )
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("photographer_workspace:booking_detail", args=[foreign_booking.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("photographer_workspace:booking_action", args=[foreign_booking.pk]), {"action": "cancel"}).status_code, 404)
        self.assertEqual(self.client.post(reverse("photographer_workspace:reschedule_session", args=[foreign_booking.pk]), data="{}", content_type="application/json").status_code, 404)
        self.assertEqual(self.client.post(reverse("photographer_workspace:constraint_action", args=[foreign_block.pk]), {"action": "delete"}).status_code, 404)
        injected = self.client.post(reverse("photographer_workspace:bookings"), {
            "action": "create_booking", "client": foreign_client.pk, "session_type": "Injected",
            "start_date": "2026-08-15", "start_time": "10:00", "end_date": "2026-08-15",
            "end_time": "11:00", "booking_status": "confirmed", "team": [foreign_member.pk],
        })
        self.assertEqual(injected.status_code, 400)
        page = self.client.get(self.url, {"view": "list", "date": "2026-08-01", "q": "TenantSecret", "member": foreign_member.pk})
        self.assertEqual(page.context["schedule_events"], [])
        self.assertNotIn(foreign_client, page.context["booking_clients"])
