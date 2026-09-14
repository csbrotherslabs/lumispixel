from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientInvoice, ClientSession, ClientTask

from .models import AutomationExecution, AutomationRule
from .services import ensure_default_rules, run_execution
from .tasks import scan_scheduled_automations


class WorkflowAutomationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="automation-owner@example.com",
            password="testpass",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.photographer = PhotographerProfile.objects.create(
            user=self.user,
            slug="automation-owner",
            onboarding_completed=True,
        )
        self.client_record = Client.objects.create(
            photographer=self.photographer,
            first_name="Avery",
            last_name="Stone",
            email="avery@example.com",
        )
        self.booking = ClientSession.objects.create(
            photographer=self.photographer,
            client=self.client_record,
            event_kind=ClientSession.EventKind.BOOKING,
            session_type="Portrait session",
            starts_at=timezone.now() + timedelta(days=3),
            booking_value="450.00",
            status=ClientSession.Status.TENTATIVE,
        )

    def test_default_launch_rules_are_created_disabled(self):
        rules = ensure_default_rules(self.photographer)
        self.assertEqual(len(rules), 7)
        self.assertEqual(AutomationRule.objects.filter(photographer=self.photographer).count(), 7)
        self.assertFalse(AutomationRule.objects.filter(photographer=self.photographer, enabled=True).exists())
        expiration_rule = AutomationRule.objects.get(
            photographer=self.photographer,
            trigger=AutomationRule.Trigger.GALLERY_EXPIRING,
        )
        self.assertEqual(expiration_rule.config["days_before"], 7)

    def test_workflows_url_is_real_automation_module_not_placeholder(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("photographer_workspace:workflows"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "photographer_workspace/workflows/index.html")
        self.assertContains(response, "Launch automations")
        self.assertContains(response, "Celery + Beat")
        self.assertNotContains(response, "Coming Soon")

    def test_owner_can_toggle_rule_and_cannot_toggle_another_workspace_rule(self):
        own_rule = ensure_default_rules(self.photographer)[0]
        other_user = User.objects.create_user(
            email="automation-other@example.com",
            password="testpass",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        other = PhotographerProfile.objects.create(user=other_user, slug="automation-other", onboarding_completed=True)
        other_rule = ensure_default_rules(other)[0]

        self.client.force_login(self.user)
        response = self.client.post(reverse("photographer_workspace:workflows"), {"rule_id": own_rule.pk, "enabled": "on"})
        self.assertRedirects(response, reverse("photographer_workspace:workflows"))
        own_rule.refresh_from_db()
        self.assertTrue(own_rule.enabled)

        self.client.post(reverse("photographer_workspace:workflows"), {"rule_id": other_rule.pk, "enabled": "on"})
        other_rule.refresh_from_db()
        self.assertFalse(other_rule.enabled)

    @patch("apps.workflows.tasks.execute_automation.delay")
    def test_booking_confirmation_queues_enabled_rule_once(self, delay):
        rule = ensure_default_rules(self.photographer)[0]
        rule.enabled = True
        rule.save(update_fields=["enabled", "updated_at"])

        self.booking.status = ClientSession.Status.CONFIRMED
        with self.captureOnCommitCallbacks(execute=True):
            self.booking.save(update_fields=["status"])
        self.assertEqual(AutomationExecution.objects.filter(rule=rule).count(), 1)
        delay.assert_called_once()

        with self.captureOnCommitCallbacks(execute=True):
            self.booking.save(update_fields=["status"])
        self.assertEqual(AutomationExecution.objects.filter(rule=rule).count(), 1)
        delay.assert_called_once()

    def test_completed_shoot_action_creates_gallery_task_idempotently(self):
        rule = ensure_default_rules(self.photographer)[4]
        execution = AutomationExecution.objects.create(
            rule=rule,
            photographer=self.photographer,
            event_key=f"manual-shoot:{self.booking.pk}",
            trigger=rule.trigger,
            target_type=self.booking._meta.label_lower,
            target_id=self.booking.pk,
        )
        performed, _ = run_execution(execution)
        self.assertTrue(performed)
        self.assertEqual(ClientTask.objects.filter(photographer=self.photographer, client=self.client_record).count(), 1)
        performed_again, _ = run_execution(execution)
        self.assertFalse(performed_again)
        self.assertEqual(ClientTask.objects.filter(photographer=self.photographer, client=self.client_record).count(), 1)

    @patch("apps.workflows.tasks.dispatch_event")
    def test_beat_scanner_finds_invoice_due_on_configured_day(self, dispatch):
        rule = ensure_default_rules(self.photographer)[2]
        rule.enabled = True
        rule.save(update_fields=["enabled", "updated_at"])
        invoice = ClientInvoice.objects.create(
            photographer=self.photographer,
            client=self.client_record,
            invoice_number="INV-AUTO-1",
            total="450.00",
            due_date=timezone.localdate() + timedelta(days=3),
        )

        scan_scheduled_automations.run()

        self.assertTrue(any(call.kwargs.get("target") == invoice for call in dispatch.call_args_list))
