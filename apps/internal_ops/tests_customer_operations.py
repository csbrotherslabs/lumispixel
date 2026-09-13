from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import ClientProfile, PhotographerProfile

from .models import Department, EmployeeProfile, InternalAuditEvent, InternalRole


User = get_user_model()


class InternalCustomerOperationsTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            email="support@lumispixel.com",
            password="test-pass-123",
            first_name="Avery",
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )
        department, _ = Department.objects.get_or_create(name="Customer Support", code="customer-support")
        role = InternalRole.objects.create(name="Customer Support Agent", code="customer-support-agent", department=department)
        self.employee = EmployeeProfile.objects.create(
            user=self.staff_user,
            employee_id="LP-CS-001",
            department=department,
            role=role,
            status=EmployeeProfile.Status.ACTIVE,
        )

        self.customer = User.objects.create_user(
            email="jordan@example.com",
            password="test-pass-123",
            first_name="Jordan",
            last_name="Lee",
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )
        self.client_profile = ClientProfile.objects.create(user=self.customer, display_name="Jordan Lee")

        self.photographer_user = User.objects.create_user(
            email="studio@example.com",
            password="test-pass-123",
            first_name="Morgan",
            last_name="Reed",
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )
        self.photographer = PhotographerProfile.objects.create(
            user=self.photographer_user,
            display_name="Morgan Reed",
            business_name="North Light Studio",
        )

    def test_active_employee_can_open_customer_directory(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("internal_ops:customers"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Customer &amp; Account Operations")
        self.assertContains(response, "jordan@example.com")
        self.assertContains(response, "North Light Studio")

    def test_customer_directory_searches_email_and_business_name(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("internal_ops:customers"), {"q": "North Light"})
        self.assertContains(response, "studio@example.com")
        self.assertNotContains(response, "jordan@example.com")

        response = self.client.get(reverse("internal_ops:customers"), {"q": "jordan@example.com"})
        self.assertContains(response, "jordan@example.com")
        self.assertNotContains(response, "studio@example.com")

    def test_customer_directory_filters_account_type(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("internal_ops:customers"), {"type": "photographer"})
        self.assertContains(response, "studio@example.com")
        self.assertNotContains(response, "jordan@example.com")

    def test_customer_detail_is_read_only_and_audited(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("internal_ops:customer_detail", args=[self.customer.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jordan Lee")
        self.assertContains(response, "Read only")
        self.assertContains(response, "Change plan")
        self.assertTrue(
            InternalAuditEvent.objects.filter(
                actor=self.employee,
                action="internal.customer.view",
                target_id=str(self.customer.pk),
            ).exists()
        )

    def test_photographer_detail_shows_plan_and_usage_sections(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("internal_ops:customer_detail", args=[self.photographer_user.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "North Light Studio")
        self.assertContains(response, "Workspace consumption")
        self.assertContains(response, "Storage used")
        self.assertContains(response, "AI actions")

    def test_non_employee_cannot_access_customer_operations(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("internal_ops:customers"))
        self.assertEqual(response.status_code, 403)

    def test_superuser_can_access_customer_operations_without_employee_profile(self):
        superuser = User.objects.create_superuser(email="ops-admin@lumispixel.com", password="test-pass-123")
        self.client.force_login(superuser)
        response = self.client.get(reverse("internal_ops:customers"))
        self.assertEqual(response.status_code, 200)
        detail = self.client.get(reverse("internal_ops:customer_detail", args=[self.customer.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(
            InternalAuditEvent.objects.filter(
                actor__isnull=True,
                action="internal.customer.view",
                target_id=str(self.customer.pk),
                metadata__superuser=True,
            ).exists()
        )
