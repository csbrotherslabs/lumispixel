from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.models import PhotographerProfile
from apps.ai_engine.models import AIJob
from apps.billing.ai_usage import get_usage_balance
from apps.billing.models import AIUsageTransaction, Plan, PlanAllowance, Subscription
from apps.billing.services import ensure_subscription
from apps.galleries.models import Gallery

from .decorators import internal_employee_required
from .governance import actor_for_request, create_approval
from .models import ApprovalRequest, Department, InternalAuditEvent
from .resource_operations import execute_ai_credit_grant, execute_plan_override


GIB = 1024 ** 3


def _format_bytes(value):
    value = int(value or 0)
    if value >= 1024 ** 4:
        return f"{value / 1024 ** 4:.1f} TB"
    if value >= GIB:
        return f"{value / GIB:.1f} GB"
    if value >= 1024 ** 2:
        return f"{value / 1024 ** 2:.1f} MB"
    if value >= 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value} B"


def _base_context(request, nav):
    return {
        "employee": actor_for_request(request),
        "is_internal_superuser": request.user.is_superuser,
        "active_nav": nav,
    }


def _photographer_rows(query="", limit=100):
    profiles = PhotographerProfile.objects.select_related("user")
    if query:
        profiles = profiles.filter(
            Q(user__email__icontains=query)
            | Q(display_name__icontains=query)
            | Q(business_name__icontains=query)
            | Q(slug__icontains=query)
        )
    rows = []
    for profile in profiles[:limit]:
        subscription = ensure_subscription(profile)
        storage = Gallery.objects.for_photographer(profile).aggregate(
            total=Coalesce(Sum("storage_used"), Value(0), output_field=DecimalField())
        )["total"]
        ai = get_usage_balance(profile)
        storage_allowance = subscription.plan.allowances.filter(key="storage_bytes").first()
        storage_limit = None
        if storage_allowance and storage_allowance.limit_type == PlanAllowance.LimitType.NUMERIC:
            storage_limit = int(storage_allowance.value or 0)
        rows.append({
            "profile": profile,
            "subscription": subscription,
            "storage_bytes": int(storage or 0),
            "storage_display": _format_bytes(storage),
            "storage_limit": storage_limit,
            "storage_limit_display": _format_bytes(storage_limit) if storage_limit is not None else (storage_allowance.get_limit_type_display() if storage_allowance else "Not configured"),
            "storage_percent": round((Decimal(storage or 0) / Decimal(storage_limit)) * 100) if storage_limit else None,
            "ai": ai,
        })
    return rows


@internal_employee_required
def ai_operations(request):
    q = request.GET.get("q", "").strip()
    jobs = AIJob.objects.select_related("photographer__user", "gallery", "usage_reservation")
    if q:
        jobs = jobs.filter(Q(photographer__user__email__icontains=q) | Q(gallery__name__icontains=q) | Q(error_summary__icontains=q))
    context = _base_context(request, "ai_operations")
    context.update({
        "query": q,
        "queued_count": AIJob.objects.filter(status=AIJob.Status.QUEUED).count(),
        "running_count": AIJob.objects.filter(status=AIJob.Status.RUNNING).count(),
        "failed_count": AIJob.objects.filter(status=AIJob.Status.FAILED).count(),
        "completed_count": AIJob.objects.filter(status=AIJob.Status.COMPLETED).count(),
        "recent_jobs": jobs[:100],
        "recent_transactions": AIUsageTransaction.objects.select_related("account__photographer__user", "operation")[:100],
        "workspace_rows": _photographer_rows(q, limit=75),
        "pending_ai_approvals": ApprovalRequest.objects.filter(kind=ApprovalRequest.Kind.AI_CREDITS, status__in=[ApprovalRequest.Status.PENDING, ApprovalRequest.Status.APPROVED]).select_related("requester_user")[:30],
    })
    return render(request, "internal_ops/resources/ai_operations.html", context)


@internal_employee_required
def storage_operations(request):
    q = request.GET.get("q", "").strip()
    galleries = Gallery.objects.select_related("photographer__user")
    if q:
        galleries = galleries.filter(Q(name__icontains=q) | Q(photographer__user__email__icontains=q))
    totals = Gallery.objects.aggregate(
        total=Coalesce(Sum("storage_used"), Value(0), output_field=DecimalField()),
        galleries=Count("pk"),
    )
    context = _base_context(request, "storage_operations")
    context.update({
        "query": q,
        "total_storage": _format_bytes(totals["total"]),
        "gallery_count": totals["galleries"],
        "largest_galleries": galleries.order_by("-storage_used")[:100],
        "workspace_rows": sorted(_photographer_rows(q, limit=100), key=lambda item: item["storage_bytes"], reverse=True),
    })
    return render(request, "internal_ops/resources/storage_operations.html", context)


@internal_employee_required
def billing_operations(request):
    q = request.GET.get("q", "").strip()
    subscriptions = Subscription.objects.select_related("photographer__user", "plan")
    if q:
        subscriptions = subscriptions.filter(Q(photographer__user__email__icontains=q) | Q(photographer__business_name__icontains=q) | Q(plan__name__icontains=q))
    plan_counts = list(
        Subscription.objects.values("plan__name", "plan__code").annotate(total=Count("pk")).order_by("plan__sort_order")
    )
    context = _base_context(request, "billing_operations")
    context.update({
        "query": q,
        "subscriptions": subscriptions[:150],
        "plans": Plan.objects.filter(is_active=True).prefetch_related("prices", "allowances").order_by("sort_order"),
        "plan_counts": plan_counts,
        "active_count": Subscription.objects.filter(status=Subscription.Status.ACTIVE).count(),
        "past_due_count": Subscription.objects.filter(status=Subscription.Status.PAST_DUE).count(),
        "provider_none_count": Subscription.objects.filter(provider=Subscription.Provider.NONE).count(),
        "pending_plan_approvals": ApprovalRequest.objects.filter(kind=ApprovalRequest.Kind.PLAN_OVERRIDE, status__in=[ApprovalRequest.Status.PENDING, ApprovalRequest.Status.APPROVED]).select_related("requester_user")[:30],
    })
    return render(request, "internal_ops/resources/billing_operations.html", context)


@internal_employee_required
@require_POST
def request_ai_credit_grant(request):
    photographer = get_object_or_404(PhotographerProfile.objects.select_related("user"), pk=request.POST.get("photographer"))
    try:
        units = int(request.POST.get("units", "0"))
    except ValueError:
        units = 0
    reason = request.POST.get("reason", "").strip()
    if units <= 0 or not reason:
        messages.error(request, "A positive credit amount and business reason are required.")
        return redirect("internal_ops:ai_operations")
    finance = Department.objects.filter(code="finance", is_active=True).first()
    approval = create_approval(
        requester_user=request.user,
        requester_employee=actor_for_request(request),
        kind=ApprovalRequest.Kind.AI_CREDITS,
        risk_level=ApprovalRequest.Risk.HIGH if units >= 10000 else ApprovalRequest.Risk.MEDIUM,
        title=f"Grant {units:,} AI credits to {photographer.business_name or photographer.user.email}",
        reason=reason,
        target_type="photographer_profile",
        target_id=str(photographer.pk),
        proposed_changes={"purchased_units": units},
        approver_department=finance,
    )
    messages.success(request, f"Approval request {approval.reference} created.")
    return redirect("internal_ops:approval_detail", reference=approval.reference)


@internal_employee_required
@require_POST
def request_plan_override(request):
    photographer = get_object_or_404(PhotographerProfile.objects.select_related("user"), pk=request.POST.get("photographer"))
    plan = get_object_or_404(Plan, code=request.POST.get("plan"), is_active=True)
    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, "A business reason is required.")
        return redirect("internal_ops:billing_operations")
    current = ensure_subscription(photographer)
    finance = Department.objects.filter(code="finance", is_active=True).first()
    approval = create_approval(
        requester_user=request.user,
        requester_employee=actor_for_request(request),
        kind=ApprovalRequest.Kind.PLAN_OVERRIDE,
        risk_level=ApprovalRequest.Risk.HIGH,
        title=f"Managed plan override: {current.plan.name} → {plan.name}",
        reason=reason,
        target_type="photographer_profile",
        target_id=str(photographer.pk),
        proposed_changes={"plan_code": plan.code, "previous_plan_code": current.plan.code},
        approver_department=finance,
    )
    messages.success(request, f"Approval request {approval.reference} created.")
    return redirect("internal_ops:approval_detail", reference=approval.reference)


def _can_execute_domain(request, approval):
    if approval.requester_user_id == request.user.pk:
        return False
    if request.user.is_superuser:
        return True
    employee = actor_for_request(request)
    if not employee or not employee.department:
        return False
    allowed = {"finance", "executive"}
    if approval.kind == ApprovalRequest.Kind.AI_CREDITS:
        allowed.add("ai-operations")
    return employee.department.code in allowed


@internal_employee_required
@require_http_methods(["GET", "POST"])
def approved_operation(request, reference):
    approval = get_object_or_404(ApprovalRequest, reference=reference)
    if approval.kind not in {ApprovalRequest.Kind.AI_CREDITS, ApprovalRequest.Kind.PLAN_OVERRIDE}:
        messages.error(request, "This approval is not executed through AI/billing operations.")
        return redirect("internal_ops:approval_detail", reference=approval.reference)
    photographer = get_object_or_404(PhotographerProfile.objects.select_related("user"), pk=approval.target_id)
    can_execute = approval.status == ApprovalRequest.Status.APPROVED and _can_execute_domain(request, approval)
    if request.method == "POST":
        if not can_execute:
            messages.error(request, "You are not permitted to execute this approved operation.")
            return redirect("internal_ops:approved_operation", reference=approval.reference)
        note = request.POST.get("note", "").strip()
        if not note:
            messages.error(request, "An execution note is required.")
            return redirect("internal_ops:approved_operation", reference=approval.reference)
        try:
            if approval.kind == ApprovalRequest.Kind.AI_CREDITS:
                execute_ai_credit_grant(
                    approval=approval,
                    photographer=photographer,
                    executor_user=request.user,
                    executor_employee=actor_for_request(request),
                    note=note,
                )
                messages.success(request, "Approved AI credit grant executed and recorded in the ledger.")
            else:
                execute_plan_override(
                    approval=approval,
                    photographer=photographer,
                    executor_user=request.user,
                    executor_employee=actor_for_request(request),
                    note=note,
                )
                messages.success(request, "Approved managed plan override executed.")
        except (ValueError, PermissionError) as exc:
            messages.error(request, str(exc))
        return redirect("internal_ops:approval_detail", reference=approval.reference)

    context = _base_context(request, "approvals")
    context.update({
        "approval": approval,
        "photographer": photographer,
        "can_execute": can_execute,
        "subscription": ensure_subscription(photographer),
        "ai_balance": get_usage_balance(photographer),
    })
    return render(request, "internal_ops/resources/approved_operation.html", context)
