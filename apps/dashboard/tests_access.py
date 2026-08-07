from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client
from apps.dashboard.access import access_for, scope_assigned, validate_assignment
from apps.dashboard.models import StudioMembership


class StudioAccessTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="owner-access@example.com", password="pass12345")
        self.owner.account_status = User.AccountStatus.ACTIVE
        self.owner.save()
        self.studio = PhotographerProfile.objects.create(user=self.owner, onboarding_completed=True)
        self.member_user = User.objects.create_user(email="member-access@example.com", password="pass12345")
        self.member_user.account_status = User.AccountStatus.ACTIVE
        self.member_user.save()
        self.membership = StudioMembership.objects.create(
            studio=self.studio, user=self.member_user, role=StudioMembership.Role.PHOTOGRAPHER,
            status=StudioMembership.Status.ACTIVE,
        )

    def test_photographer_queries_include_only_assigned_studio_records(self):
        assigned = Client.objects.create(photographer=self.studio, first_name="Assigned")
        Client.objects.create(photographer=self.studio, first_name="Private")
        assigned.assigned_members.add(self.membership)
        self.assertEqual(list(scope_assigned(Client.objects.all(), access_for(self.member_user))), [assigned])

    def test_inactive_membership_cannot_resolve_access(self):
        self.membership.status = StudioMembership.Status.SUSPENDED
        self.membership.save()
        with self.assertRaises(PermissionDenied):
            access_for(self.member_user)

    def test_member_without_financial_access_receives_no_overview_payload(self):
        self.client.force_login(self.member_user)

        response = self.client.get(reverse("photographer_workspace:financial_overview"))

        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, "Financial Overview", status_code=403)
        self.assertNotContains(response, "Revenue", status_code=403)

    def test_cross_studio_assignment_is_rejected_by_service(self):
        other_owner = User.objects.create_user(email="other-access@example.com", password="pass12345")
        other = PhotographerProfile.objects.create(user=other_owner)
        record = Client.objects.create(photographer=other, first_name="Other")
        with self.assertRaises(ValidationError):
            validate_assignment(self.membership, record)
