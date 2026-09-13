from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import PhotographerProfile
from apps.billing.models import AIUsageAccount, AIUsageTransaction, Plan, Subscription

from .governance import decide_approval
from .models import ApprovalRequest, Department, EmployeeProfile, InternalAuditEvent, InternalRole


User = get_user_model()


class InternalResourceOperationsTests(TestCase):
    def setUp(self):
        self.ai_department, _ = Department.objects.get_or_create(name="AI Operations", code="ai-operations")
        self.finance_department, _ = Department.objects.get_or_create(name="Finance", code="finance")
        self.ai_role = InternalRole.objects.create(name="AI Operator 8F", code="ai-operator-8f", department=self.ai_department)
        self.finance_role = InternalRole.objects.create(name="Finance Operator 8F", code="finance-operator-8f", department=self.finance_department)
        self.requester_user = User.objects.create_user(email="ai-ops-8f@lumispixel.com", password="test-pass-123", first_name="Ari", account_status=User.AccountStatus.ACTIVE, email_verified=True)
        self.requester = EmployeeProfile.objects.create(user=self.requester_user, employee_id="LP-AI-8F", department=self.ai_department, role=self.ai_role, status=EmployeeProfile.Status.ACTIVE)
        self.finance_user = User.objects.create_user(email="finance-8f@lumispixel.com", password="test-pass-123", first_name="Fin", account_status=User.AccountStatus.ACTIVE, email_verified=True)
        self.finance = EmployeeProfile.objects.create(user=self.finance_user, employee_id="LP-FIN-8F", department=self.finance_department, role=self.finance_role, status=EmployeeProfile.Status.ACTIVE)
        self.customer_user = User.objects.create_user(email="studio-8f@example.com", password="test-pass-123", first_name="Morgan", primary_role=User.PrimaryRole.PHOTOGRAPHER, account_status=User.AccountStatus.ACTIVE, email_verified=True)
        self.photographer = PhotographerProfile.objects.create(user=self.customer_user, display_name="Morgan Studio", business_name="Morgan Studio", slug="morgan-studio-8f")

    def test_internal_resource_dashboards_require_employee_access(self):
        self.client.force_login(self.customer_user)
        for name in ("internal_ops:ai_operations", "internal_ops:storage_operations", "internal_ops:billing_operations"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)
        self.client.force_login(self.requester_user)
        for name in ("internal_ops:ai_operations", "internal_ops:storage_operations", "internal_ops:billing_operations"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_ai_credit_request_requires_approval_before_balance_changes(self):
        account, _ = AIUsageAccount.objects.get_or_create(photographer=self.photographer)
        self.assertEqual(account.purchased_balance, 0)
        self.client.force_login(self.requester_user)
        response = self.client.post(reverse("internal_ops:request_ai_credit_grant"), {
            "photographer": self.photographer.pk,
            "units": "2500",
            "reason": "Service recovery credit for a verified processing incident.",
        })
        approval = ApprovalRequest.objects.get(kind=ApprovalRequest.Kind.AI_CREDITS)
        self.assertRedirects(response, reverse("internal_ops:approval_detail", args=[approval.reference]))
        account.refresh_from_db()
        self.assertEqual(account.purchased_balance, 0)
        self.assertEqual(approval.status, ApprovalRequest.Status.PENDING)
        self.assertEqual(approval.approver_department, self.finance_department)

    def test_approved_ai_credit_grant_executes_ledger_and_audit_atomically(self):
        approval = ApprovalRequest.objects.create(
            requester=self.requester,
            requester_user=self.requester_user,
            kind=ApprovalRequest.Kind.AI_CREDITS,
            risk_level=ApprovalRequest.Risk.MEDIUM,
            title="Grant recovery credits",
            reason="Verified support recovery.",
            target_type="photographer_profile",
            target_id=str(self.photographer.pk),
            proposed_changes={"purchased_units": 3000},
            approver_department=self.finance_department,
        )
        decide_approval(approval=approval, reviewer_user=self.finance_user, reviewer_employee=self.finance, decision=ApprovalRequest.Status.APPROVED, note="Approved after incident verification.")
        self.client.force_login(self.finance_user)
        response = self.client.post(reverse("internal_ops:approved_operation", args=[approval.reference]), {"note": "Executed approved service recovery grant."})
        self.assertEqual(response.status_code, 302)
        approval.refresh_from_db()
        account = AIUsageAccount.objects.get(photographer=self.photographer)
        self.assertEqual(approval.status, ApprovalRequest.Status.EXECUTED)
        self.assertEqual(account.purchased_balance, 3000)
        tx = AIUsageTransaction.objects.get(idempotency_key=f"approval:{approval.reference}:ai-credit-grant")
        self.assertEqual(tx.kind, AIUsageTransaction.Kind.PURCHASE_GRANT)
        self.assertEqual(tx.purchased_units, 3000)
        self.assertTrue(InternalAuditEvent.objects.filter(action="internal.ai.credit_grant.execute", target_id=str(self.photographer.pk)).exists())

    def test_requester_cannot_execute_own_approved_ai_grant(self):
        approval = ApprovalRequest.objects.create(
            requester=self.requester,
            requester_user=self.requester_user,
            kind=ApprovalRequest.Kind.AI_CREDITS,
            risk_level=ApprovalRequest.Risk.MEDIUM,
            status=ApprovalRequest.Status.APPROVED,
            title="Self execution blocked",
            reason="Control test",
            target_type="photographer_profile",
            target_id=str(self.photographer.pk),
            proposed_changes={"purchased_units": 100},
            approver_department=self.finance_department,
        )
        self.client.force_login(self.requester_user)
        response = self.client.post(reverse("internal_ops:approved_operation", args=[approval.reference]), {"note": "Attempt self execution"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AIUsageTransaction.objects.filter(source_reference=approval.reference).exists())

    def test_approved_plan_override_changes_authoritative_subscription(self):
        target = Plan.objects.get(code="pro")
        current = Subscription.objects.get(photographer=self.photographer)
        self.assertNotEqual(current.plan, target)
        approval = ApprovalRequest.objects.create(
            requester=self.requester,
            requester_user=self.requester_user,
            kind=ApprovalRequest.Kind.PLAN_OVERRIDE,
            risk_level=ApprovalRequest.Risk.HIGH,
            title="Managed Pro override",
            reason="Sales-assisted temporary plan assignment.",
            target_type="photographer_profile",
            target_id=str(self.photographer.pk),
            proposed_changes={"plan_code": target.code, "previous_plan_code": current.plan.code},
            approver_department=self.finance_department,
        )
        decide_approval(approval=approval, reviewer_user=self.finance_user, reviewer_employee=self.finance, decision=ApprovalRequest.Status.APPROVED, note="Approved managed override.")
        self.client.force_login(self.finance_user)
        self.client.post(reverse("internal_ops:approved_operation", args=[approval.reference]), {"note": "Executed managed override after approval."})
        approval.refresh_from_db()
        current.refresh_from_db()
        self.assertEqual(approval.status, ApprovalRequest.Status.EXECUTED)
        self.assertEqual(current.plan.code, "pro")
        self.assertEqual(current.provider, Subscription.Provider.NONE)
        self.assertTrue(InternalAuditEvent.objects.filter(action="internal.billing.plan_override.execute", target_id=str(self.photographer.pk)).exists())
