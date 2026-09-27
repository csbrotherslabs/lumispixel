from django.db import transaction

from apps.billing.models import AIUsageAccount, AIUsageTransaction, Plan, Subscription
from apps.billing.services import select_plan

from .governance import mark_approval_executed, record_audit
from .models import ApprovalRequest, InternalAuditEvent


def _assert_approved(approval, *, kind, target_type, target_id):
    if approval.status != ApprovalRequest.Status.APPROVED:
        raise ValueError("This operation requires an approved request.")
    if approval.kind != kind:
        raise ValueError("Approval type does not match this operation.")
    if approval.target_type != target_type or str(approval.target_id) != str(target_id):
        raise ValueError("Approval target does not match this operation.")


@transaction.atomic
def execute_ai_credit_grant(*, approval, photographer, executor_user, executor_employee, note):
    approval = ApprovalRequest.objects.select_for_update().get(pk=approval.pk)
    _assert_approved(
        approval,
        kind=ApprovalRequest.Kind.AI_CREDITS,
        target_type="photographer_profile",
        target_id=photographer.pk,
    )
    units = int((approval.proposed_changes or {}).get("purchased_units", 0))
    if units <= 0:
        raise ValueError("Approved AI credit grants must contain a positive purchased_units value.")

    key = f"approval:{approval.reference}:ai-credit-grant"
    existing = AIUsageTransaction.objects.filter(idempotency_key=key).first()
    if existing:
        return existing

    account, _ = AIUsageAccount.objects.get_or_create(photographer=photographer)
    account = AIUsageAccount.objects.select_for_update().get(pk=account.pk)
    account.purchased_balance += units
    account.save(update_fields=["purchased_balance", "updated_at"])

    tx = AIUsageTransaction.objects.create(
        account=account,
        period=None,
        operation=None,
        kind=AIUsageTransaction.Kind.PURCHASE_GRANT,
        included_units=0,
        purchased_units=units,
        idempotency_key=key,
        source_reference=approval.reference,
        metadata={"approval_reference": approval.reference, "internal_grant": True},
    )
    record_audit(
        actor=executor_employee,
        category=InternalAuditEvent.Category.AI,
        action="internal.ai.credit_grant.execute",
        target_type="photographer_profile",
        target_id=photographer.pk,
        summary=f"Granted {units:,} purchased AI units via {approval.reference}",
        reason=note,
        metadata={"approval_reference": approval.reference, "units": units, "transaction_id": tx.pk},
    )
    mark_approval_executed(
        approval=approval,
        executor_user=executor_user,
        executor_employee=executor_employee,
        execution_note=note,
        execution_metadata={"ai_transaction_id": tx.pk, "units": units},
    )
    return tx


@transaction.atomic
def execute_plan_override(*, approval, photographer, executor_user, executor_employee, note):
    approval = ApprovalRequest.objects.select_for_update().get(pk=approval.pk)
    _assert_approved(
        approval,
        kind=ApprovalRequest.Kind.PLAN_OVERRIDE,
        target_type="photographer_profile",
        target_id=photographer.pk,
    )
    plan_code = str((approval.proposed_changes or {}).get("plan_code", "")).strip().lower()
    if not plan_code:
        raise ValueError("Approved plan overrides must contain plan_code.")
    plan = Plan.objects.filter(code=plan_code, is_active=True).first()
    if plan is None:
        raise ValueError("The approved plan is no longer active.")

    previous = Subscription.objects.filter(photographer=photographer).select_related("plan").first()
    previous_code = previous.plan.code if previous else None
    subscription = select_plan(photographer, plan_code, enforce_customer_selectable=False)
    record_audit(
        actor=executor_employee,
        category=InternalAuditEvent.Category.BILLING,
        action="internal.billing.plan_override.execute",
        target_type="photographer_profile",
        target_id=photographer.pk,
        summary=f"Changed plan from {previous_code or 'none'} to {subscription.plan.code} via {approval.reference}",
        reason=note,
        metadata={"approval_reference": approval.reference, "before_plan": previous_code, "after_plan": subscription.plan.code},
    )
    mark_approval_executed(
        approval=approval,
        executor_user=executor_user,
        executor_employee=executor_employee,
        execution_note=note,
        execution_metadata={"before_plan": previous_code, "after_plan": subscription.plan.code},
    )
    return subscription
