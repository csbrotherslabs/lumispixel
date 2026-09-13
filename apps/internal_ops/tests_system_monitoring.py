from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import ClientProfile
from apps.notifications.models import Notification

from .models import Department, EmployeeProfile, InternalAuditEvent, InternalRole, SupportTicket, SystemAlert
from .system_monitoring import run_system_monitoring


User = get_user_model()


class SystemMonitoringTests(TestCase):
    def setUp(self):
        self.support_department, _ = Department.objects.get_or_create(name="Customer Support", code="customer-support")
        self.engineering_department, _ = Department.objects.get_or_create(name="Engineering", code="engineering")
        self.executive_department, _ = Department.objects.get_or_create(name="Executive", code="executive")
        self.role = InternalRole.objects.create(name="System Monitor Operator", code="system-monitor-operator", department=self.support_department)
        self.staff_user = User.objects.create_user(
            email="monitor-support@lumispixel.com", password="test-pass-123", first_name="Avery",
            account_status=User.AccountStatus.ACTIVE, email_verified=True,
        )
        self.employee = EmployeeProfile.objects.create(
            user=self.staff_user, employee_id="LP-MON-100", department=self.support_department,
            role=self.role, status=EmployeeProfile.Status.ACTIVE,
        )
        self.customer = User.objects.create_user(
            email="monitor-customer@example.com", password="test-pass-123", first_name="Jordan",
            account_status=User.AccountStatus.ACTIVE, email_verified=True,
        )
        ClientProfile.objects.create(user=self.customer, display_name="Jordan")

    def _urgent_ticket(self, **kwargs):
        defaults = {
            "requester": self.customer,
            "requester_type": "client",
            "category": SupportTicket.Category.TECHNICAL,
            "subject": "Urgent monitoring test",
            "description": "Monitoring test",
            "priority": SupportTicket.Priority.URGENT,
            "queue": self.support_department,
        }
        defaults.update(kwargs)
        return SupportTicket.objects.create(**defaults)

    def test_monitor_creates_deduplicated_alert_and_internal_notification(self):
        self._urgent_ticket()
        run_system_monitoring()
        alert = SystemAlert.objects.get(key="support.urgent_unassigned")
        self.assertEqual(alert.status, SystemAlert.Status.OPEN)
        self.assertEqual(alert.severity, SystemAlert.Severity.WARNING)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.staff_user,
                metadata__system_alert_key="support.urgent_unassigned",
            ).exists()
        )
        first_notification_count = Notification.objects.filter(recipient=self.staff_user).count()
        run_system_monitoring()
        self.assertEqual(SystemAlert.objects.filter(key="support.urgent_unassigned").count(), 1)
        self.assertEqual(Notification.objects.filter(recipient=self.staff_user).count(), first_notification_count)

    def test_monitor_auto_resolves_recovered_condition(self):
        ticket = self._urgent_ticket()
        run_system_monitoring()
        ticket.assignee = self.employee
        ticket.save(update_fields=["assignee", "updated_at"])
        run_system_monitoring()
        alert = SystemAlert.objects.get(key="support.urgent_unassigned")
        self.assertEqual(alert.status, SystemAlert.Status.RESOLVED)
        self.assertIsNotNone(alert.resolved_at)

    def test_overdue_ticket_creates_support_alert(self):
        self._urgent_ticket(priority=SupportTicket.Priority.NORMAL, due_at=timezone.now() - timedelta(hours=2))
        results = run_system_monitoring()
        self.assertTrue(any(item["key"] == "support.overdue" and not item["healthy"] for item in results))
        self.assertTrue(SystemAlert.objects.filter(key="support.overdue", status=SystemAlert.Status.OPEN).exists())

    def test_employee_can_run_checks_and_acknowledge_alert(self):
        self._urgent_ticket()
        self.client.force_login(self.staff_user)
        response = self.client.post(reverse("internal_ops:system"), {"action": "run_checks"})
        self.assertEqual(response.status_code, 200)
        alert = SystemAlert.objects.get(key="support.urgent_unassigned")
        response = self.client.post(reverse("internal_ops:system_alert_action", args=[alert.pk]), {"action": "acknowledge"})
        self.assertEqual(response.status_code, 302)
        alert.refresh_from_db()
        self.assertEqual(alert.status, SystemAlert.Status.ACKNOWLEDGED)
        self.assertEqual(alert.acknowledged_by, self.employee)
        self.assertTrue(InternalAuditEvent.objects.filter(action="internal.system.alert.acknowledge", target_id=str(alert.pk)).exists())

    def test_non_employee_cannot_open_system_monitor(self):
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse("internal_ops:system")).status_code, 403)

    def test_management_command_runs_monitoring(self):
        self._urgent_ticket()
        call_command("run_internal_monitoring", verbosity=0)
        self.assertTrue(SystemAlert.objects.filter(key="support.urgent_unassigned").exists())

    def test_new_support_ticket_creates_internal_inbox_notification(self):
        self.client.force_login(self.customer)
        response = self.client.post(reverse("support_help_center"), {
            "category": SupportTicket.Category.ACCOUNT,
            "subject": "Internal notification test",
            "description": "Please route this to support.",
            "related_url": "",
        })
        self.assertEqual(response.status_code, 302)
        ticket = SupportTicket.objects.get(requester=self.customer, subject="Internal notification test")
        notification = Notification.objects.get(recipient=self.staff_user, metadata__support_ticket_reference=ticket.reference)
        self.assertEqual(notification.action_url, f"/internal/tickets/{ticket.reference}/")
        self.assertIn("New support ticket", notification.title)
