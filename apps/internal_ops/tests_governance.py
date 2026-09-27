from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.notifications.models import Notification

from .models import ApprovalRequest, Department, EmployeeProfile, InternalAuditEvent, InternalRole


User = get_user_model()


class GovernanceTests(TestCase):
    def setUp(self):
        self.support, _ = Department.objects.get_or_create(name="Customer Support", code="customer-support")
        self.finance, _ = Department.objects.get_or_create(name="Finance", code="finance")
        self.engineering, _ = Department.objects.get_or_create(name="Engineering", code="engineering")

        self.request_role = InternalRole.objects.create(name="Support Agent Governance", code="support-agent-governance", department=self.support)
        self.finance_role = InternalRole.objects.create(name="Finance Approver Governance", code="finance-approver-governance", department=self.finance)
        self.engineering_role = InternalRole.objects.create(name="Engineer Governance", code="engineer-governance", department=self.engineering)

        self.requester_user = User.objects.create_user(
            email="approval-requester@lumispixel.com", password="test-pass-123", first_name="Riley",
            account_status=User.AccountStatus.ACTIVE, email_verified=True,
        )
        self.requester = EmployeeProfile.objects.create(
            user=self.requester_user, employee_id="LP-GOV-REQ", department=self.support,
            role=self.request_role, status=EmployeeProfile.Status.ACTIVE,
        )

        self.approver_user = User.objects.create_user(
            email="approval-reviewer@lumispixel.com", password="test-pass-123", first_name="Morgan",
            account_status=User.AccountStatus.ACTIVE, email_verified=True,
        )
        self.approver = EmployeeProfile.objects.create(
            user=self.approver_user, employee_id="LP-GOV-APR", department=self.finance,
            role=self.finance_role, status=EmployeeProfile.Status.ACTIVE,
        )

        self.other_user = User.objects.create_user(
            email="approval-other@lumispixel.com", password="test-pass-123", first_name="Avery",
            account_status=User.AccountStatus.ACTIVE, email_verified=True,
        )
        self.other = EmployeeProfile.objects.create(
            user=self.other_user, employee_id="LP-GOV-OTH", department=self.engineering,
            role=self.engineering_role, status=EmployeeProfile.Status.ACTIVE,
        )

        self.customer_user = User.objects.create_user(
            email="not-internal@example.com", password="test-pass-123", first_name="Customer",
            account_status=User.AccountStatus.ACTIVE, email_verified=True,
        )

    def _create_approval_via_view(self):
        self.client.force_login(self.requester_user)
        response = self.client.post(
            reverse("internal_ops:approval_create"),
            {
                "kind": ApprovalRequest.Kind.AI_CREDITS,
                "risk_level": ApprovalRequest.Risk.HIGH,
                "title": "Grant 20,000 complimentary AI credits",
                "reason": "Customer recovery after a verified service incident.",
                "target_type": "accounts.User",
                "target_id": str(self.customer_user.pk),
                "approver_department": str(self.finance.pk),
                "proposed_changes": '{"ai_credits": 20000}',
            },
        )
        self.assertEqual(response.status_code, 302)
        return ApprovalRequest.objects.get(requester_user=self.requester_user)

    def test_internal_employee_can_open_audit_and_approval_pages(self):
        self.client.force_login(self.requester_user)
        self.assertEqual(self.client.get(reverse("internal_ops:audit")).status_code, 200)
        self.assertEqual(self.client.get(reverse("internal_ops:approvals")).status_code, 200)
        self.assertEqual(self.client.get(reverse("internal_ops:approval_create")).status_code, 200)

    def test_non_employee_cannot_access_governance(self):
        self.client.force_login(self.customer_user)
        self.assertEqual(self.client.get(reverse("internal_ops:audit")).status_code, 403)
        self.assertEqual(self.client.get(reverse("internal_ops:approvals")).status_code, 403)

    def test_create_approval_records_audit_and_notifies_approver_department(self):
        approval = self._create_approval_via_view()
        self.assertEqual(approval.status, ApprovalRequest.Status.PENDING)
        self.assertEqual(approval.proposed_changes["ai_credits"], 20000)
        self.assertTrue(
            InternalAuditEvent.objects.filter(
                action="approval.request.create", target_id=approval.reference, actor=self.requester
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.approver_user,
                metadata__approval_reference=approval.reference,
            ).exists()
        )
        self.assertFalse(
            Notification.objects.filter(
                recipient=self.requester_user,
                metadata__approval_reference=approval.reference,
                title__startswith="Approval needed",
            ).exists()
        )

    def test_requester_cannot_approve_own_request(self):
        approval = self._create_approval_via_view()
        self.client.force_login(self.requester_user)
        response = self.client.post(
            reverse("internal_ops:approval_detail", args=[approval.reference]),
            {"action": "approved", "note": "Self approval should be blocked."},
        )
        self.assertEqual(response.status_code, 302)
        approval.refresh_from_db()
        self.assertEqual(approval.status, ApprovalRequest.Status.PENDING)
        self.assertFalse(InternalAuditEvent.objects.filter(action="approval.request.approved", target_id=approval.reference).exists())

    def test_wrong_department_cannot_review_request(self):
        approval = self._create_approval_via_view()
        self.client.force_login(self.other_user)
        self.client.post(
            reverse("internal_ops:approval_detail", args=[approval.reference]),
            {"action": "approved", "note": "Engineering should not approve a Finance-routed request."},
        )
        approval.refresh_from_db()
        self.assertEqual(approval.status, ApprovalRequest.Status.PENDING)

    def test_authorized_reviewer_can_approve_with_reason_and_requester_is_notified(self):
        approval = self._create_approval_via_view()
        self.client.force_login(self.approver_user)
        response = self.client.post(
            reverse("internal_ops:approval_detail", args=[approval.reference]),
            {"action": "approved", "note": "Incident evidence supports this customer recovery grant."},
        )
        self.assertEqual(response.status_code, 302)
        approval.refresh_from_db()
        self.assertEqual(approval.status, ApprovalRequest.Status.APPROVED)
        self.assertEqual(approval.reviewed_by, self.approver)
        self.assertTrue(approval.reviewed_at)
        self.assertTrue(
            InternalAuditEvent.objects.filter(
                action="approval.request.approved", target_id=approval.reference, actor=self.approver
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.requester_user,
                metadata__approval_reference=approval.reference,
                title__icontains="approved",
            ).exists()
        )

    def test_requester_cannot_mark_approved_request_executed(self):
        approval = self._create_approval_via_view()
        approval.status = ApprovalRequest.Status.APPROVED
        approval.save(update_fields=["status", "updated_at"])
        self.client.force_login(self.requester_user)
        self.client.post(
            reverse("internal_ops:approval_detail", args=[approval.reference]),
            {"action": "executed", "note": "Requester should not execute this."},
        )
        approval.refresh_from_db()
        self.assertEqual(approval.status, ApprovalRequest.Status.APPROVED)

    def test_different_employee_can_mark_approved_request_executed_and_audit_it(self):
        approval = self._create_approval_via_view()
        approval.status = ApprovalRequest.Status.APPROVED
        approval.reviewed_by = self.approver
        approval.reviewed_by_user = self.approver_user
        approval.save(update_fields=["status", "reviewed_by", "reviewed_by_user", "updated_at"])
        self.client.force_login(self.approver_user)
        response = self.client.post(
            reverse("internal_ops:approval_detail", args=[approval.reference]),
            {"action": "executed", "note": "Credit ledger adjustment completed under the approved request."},
        )
        self.assertEqual(response.status_code, 302)
        approval.refresh_from_db()
        self.assertEqual(approval.status, ApprovalRequest.Status.EXECUTED)
        self.assertTrue(approval.executed_at)
        self.assertTrue(
            InternalAuditEvent.objects.filter(
                action="approval.request.executed", target_id=approval.reference, actor=self.approver
            ).exists()
        )

    def test_audit_csv_export_is_logged(self):
        InternalAuditEvent.objects.create(
            actor=self.requester,
            category=InternalAuditEvent.Category.SUPPORT,
            action="test.audit.event",
            target_type="test",
            target_id="123",
            summary="Test audit export row",
        )
        self.client.force_login(self.requester_user)
        response = self.client.get(reverse("internal_ops:audit_export"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn(b"test.audit.event", response.content)
        self.assertTrue(
            InternalAuditEvent.objects.filter(action="audit.export.csv", actor=self.requester).exists()
        )

    def test_profileless_superuser_can_view_governance_but_cannot_self_approve(self):
        admin = User.objects.create_superuser(email="governance-admin@lumispixel.com", password="test-pass-123")
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("internal_ops:audit")).status_code, 200)
        response = self.client.post(
            reverse("internal_ops:approval_create"),
            {
                "kind": ApprovalRequest.Kind.OTHER,
                "risk_level": ApprovalRequest.Risk.CRITICAL,
                "title": "Emergency governance test",
                "reason": "Exercise separation of duties for profile-less superusers.",
                "target_type": "system",
                "target_id": "emergency-test",
                "approver_department": "",
                "proposed_changes": "{}",
            },
        )
        self.assertEqual(response.status_code, 302)
        approval = ApprovalRequest.objects.get(requester_user=admin)
        self.client.post(
            reverse("internal_ops:approval_detail", args=[approval.reference]),
            {"action": "approved", "note": "Self approval must still fail."},
        )
        approval.refresh_from_db()
        self.assertEqual(approval.status, ApprovalRequest.Status.PENDING)
