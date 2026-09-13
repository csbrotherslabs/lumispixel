from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .employee_services import EmployeeManagementError, create_employee, is_employee_manager, update_employee
from .models import Department, EmployeeProfile, InternalAuditEvent, InternalRole

User = get_user_model()


class EmployeeManagementTests(TestCase):
    def setUp(self):
        self.hr_department, _ = Department.objects.get_or_create(
            code="human-resources",
            defaults={"name": "Human Resources"},
        )
        self.executive_department, _ = Department.objects.get_or_create(
            code="executive",
            defaults={"name": "Executive"},
        )
        self.engineering_department, _ = Department.objects.get_or_create(
            code="engineering",
            defaults={"name": "Engineering"},
        )
        self.hr_user = self._user("hr@lumispixel.test", "Helen", "HR")
        self.hr_employee = EmployeeProfile.objects.create(
            user=self.hr_user,
            employee_id="LP-HR-001",
            title="People Operations",
            department=self.hr_department,
            status=EmployeeProfile.Status.ACTIVE,
        )
        self.executive_user = self._user("exec@lumispixel.test", "Evan", "Executive")
        self.executive_employee = EmployeeProfile.objects.create(
            user=self.executive_user,
            employee_id="LP-EX-001",
            title="COO",
            department=self.executive_department,
            status=EmployeeProfile.Status.ACTIVE,
        )
        self.regular_user = self._user("engineer@lumispixel.test", "Riley", "Engineer")
        self.regular_employee = EmployeeProfile.objects.create(
            user=self.regular_user,
            employee_id="LP-EN-001",
            title="Engineer",
            department=self.engineering_department,
            status=EmployeeProfile.Status.ACTIVE,
        )

    def _user(self, email, first_name="Test", last_name="User"):
        return User.objects.create_user(
            email=email,
            password="Pass1234!",
            first_name=first_name,
            last_name=last_name,
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )

    def test_employee_navigation_directory_is_available_to_active_employee(self):
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("internal_ops:employees"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Employee directory")
        self.assertContains(response, self.hr_user.email)
        self.assertNotContains(response, "Add employee</a>")

    def test_hr_executive_and_superuser_are_employee_managers(self):
        self.assertTrue(is_employee_manager(self.hr_user, self.hr_employee))
        self.assertTrue(is_employee_manager(self.executive_user, self.executive_employee))
        self.assertFalse(is_employee_manager(self.regular_user, self.regular_employee))
        superuser = User.objects.create_superuser(email="root@lumispixel.test", password="Pass1234!")
        self.assertTrue(is_employee_manager(superuser, None))

    def test_regular_employee_cannot_open_add_employee(self):
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("internal_ops:employee_create"))
        self.assertEqual(response.status_code, 403)

    @patch("apps.internal_ops.employee_views.send_employee_invitation")
    def test_hr_can_create_employee_and_creation_is_audited(self, send_invitation):
        self.client.force_login(self.hr_user)
        response = self.client.post(reverse("internal_ops:employee_create"), {
            "first_name": "Avery",
            "last_name": "Support",
            "email": "avery@lumispixel.test",
            "employee_id": "lp-cs-101",
            "title": "Support Specialist",
            "department": self.engineering_department.pk,
            "role": "",
            "manager": "",
            "hire_date": "2026-09-15",
        })
        employee = EmployeeProfile.objects.get(employee_id="LP-CS-101")
        self.assertRedirects(response, reverse("internal_ops:employee_detail", args=[employee.employee_id]))
        self.assertEqual(employee.user.email, "avery@lumispixel.test")
        self.assertEqual(employee.status, EmployeeProfile.Status.ACTIVE)
        self.assertFalse(employee.user.has_usable_password())
        self.assertTrue(InternalAuditEvent.objects.filter(action="employee.created", target_id="LP-CS-101", actor=self.hr_employee).exists())
        send_invitation.assert_called_once()

    @patch("apps.internal_ops.employee_views.send_employee_invitation")
    def test_existing_lumispixel_user_is_linked_without_replacing_account(self, send_invitation):
        existing = self._user("existing@lumispixel.test", "Existing", "Customer")
        self.client.force_login(self.executive_user)
        response = self.client.post(reverse("internal_ops:employee_create"), {
            "first_name": "Existing",
            "last_name": "Customer",
            "email": existing.email,
            "employee_id": "LP-OPS-202",
            "title": "Operations Analyst",
            "department": self.engineering_department.pk,
            "role": "",
            "manager": "",
            "hire_date": "",
        })
        self.assertEqual(response.status_code, 302)
        existing.refresh_from_db()
        self.assertTrue(existing.has_usable_password())
        self.assertEqual(existing.employee_profile.employee_id, "LP-OPS-202")
        send_invitation.assert_called_once()
        self.assertFalse(send_invitation.call_args.kwargs["created_user"])

    def test_hr_cannot_assign_executive_role(self):
        executive_role = InternalRole.objects.create(name="Executive", code="executive-lead", is_executive=True)
        with self.assertRaises(PermissionError):
            create_employee(
                actor_user=self.hr_user,
                actor_employee=self.hr_employee,
                email="newexec@lumispixel.test",
                first_name="New",
                last_name="Exec",
                employee_id="LP-EX-099",
                title="Executive",
                department=self.executive_department,
                role=executive_role,
            )
        self.assertFalse(EmployeeProfile.objects.filter(employee_id="LP-EX-099").exists())

    def test_executive_can_assign_executive_role(self):
        executive_role = InternalRole.objects.create(name="Executive", code="executive-lead", is_executive=True)
        employee, _ = create_employee(
            actor_user=self.executive_user,
            actor_employee=self.executive_employee,
            email="newexec@lumispixel.test",
            first_name="New",
            last_name="Exec",
            employee_id="LP-EX-099",
            title="Executive",
            department=self.executive_department,
            role=executive_role,
        )
        self.assertEqual(employee.role, executive_role)

    def test_manager_cannot_suspend_own_employee_access(self):
        with self.assertRaises(EmployeeManagementError):
            update_employee(
                employee=self.hr_employee,
                actor_user=self.hr_user,
                actor_employee=self.hr_employee,
                first_name=self.hr_user.first_name,
                last_name=self.hr_user.last_name,
                title=self.hr_employee.title,
                department=self.hr_department,
                role=None,
                manager=None,
                status=EmployeeProfile.Status.SUSPENDED,
                hire_date=None,
                reason="Testing self suspension",
            )

    def test_employee_update_records_before_and_after_audit_state(self):
        updated = update_employee(
            employee=self.regular_employee,
            actor_user=self.hr_user,
            actor_employee=self.hr_employee,
            first_name="Riley",
            last_name="Engineer",
            title="Senior Engineer",
            department=self.engineering_department,
            role=None,
            manager=self.executive_employee,
            status=EmployeeProfile.Status.ACTIVE,
            hire_date=None,
            reason="Promotion and reporting-line update",
        )
        self.assertEqual(updated.title, "Senior Engineer")
        event = InternalAuditEvent.objects.get(action="employee.updated", target_id=self.regular_employee.employee_id)
        self.assertEqual(event.reason, "Promotion and reporting-line update")
        self.assertEqual(event.metadata["before"]["title"], "Engineer")
        self.assertEqual(event.metadata["after"]["title"], "Senior Engineer")
