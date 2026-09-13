from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Department, EmployeeProfile, InternalAuditEvent, InternalRole


User = get_user_model()


class InternalWorkspaceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="employee@lumispixel.com",
            password="test-pass-123",
            first_name="Alex",
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )
        self.department = Department.objects.create(name="Customer Support", code="customer-support")
        self.role = InternalRole.objects.create(name="Support Specialist", code="support-specialist", department=self.department)
        self.employee = EmployeeProfile.objects.create(
            user=self.user,
            employee_id="LP-0001",
            title="Support Specialist",
            department=self.department,
            role=self.role,
            status=EmployeeProfile.Status.ACTIVE,
        )

    def test_active_employee_can_open_internal_workspace(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("internal_ops:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "LumisPixel Internal")
        self.assertContains(response, "Command Center")
        self.assertTrue(
            InternalAuditEvent.objects.filter(
                actor=self.employee,
                action="internal.dashboard.view",
            ).exists()
        )

    def test_superuser_without_employee_profile_can_open_internal_workspace(self):
        superuser = User.objects.create_superuser(
            email="admin@lumispixel.com",
            password="test-pass-123",
            first_name="Admin",
        )
        self.client.force_login(superuser)
        response = self.client.get(reverse("internal_ops:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Superuser")
        self.assertContains(response, "Full LumisPixel Internal access")
        self.assertTrue(
            InternalAuditEvent.objects.filter(
                actor__isnull=True,
                action="internal.dashboard.view",
                metadata__superuser=True,
            ).exists()
        )

    def test_non_employee_is_forbidden(self):
        outsider = User.objects.create_user(
            email="customer@example.com",
            password="test-pass-123",
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )
        self.client.force_login(outsider)
        response = self.client.get(reverse("internal_ops:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_suspended_employee_is_forbidden(self):
        self.employee.status = EmployeeProfile.Status.SUSPENDED
        self.employee.save(update_fields=["status", "updated_at"])
        self.client.force_login(self.user)
        response = self.client.get(reverse("internal_ops:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("internal_ops:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_employee_navigation_entry_is_visible(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:index"))
        self.assertContains(response, "LumisPixel Internal")

    def test_superuser_navigation_entry_is_visible_without_employee_profile(self):
        superuser = User.objects.create_superuser(
            email="admin-nav@lumispixel.com",
            password="test-pass-123",
        )
        self.client.force_login(superuser)
        response = self.client.get(reverse("core:index"))
        self.assertContains(response, "LumisPixel Internal")
