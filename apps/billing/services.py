from dataclasses import dataclass

from django.db import transaction

from .models import Plan, PlanAllowance, Subscription


class PlanUnavailableError(ValueError):
    """Raised when a customer attempts to select a plan that is not launch-enabled."""


class PlanConfigurationError(RuntimeError):
    """Raised when required billing catalog configuration is missing."""


@dataclass(frozen=True)
class AllowanceValue:
    key: str
    limit_type: str
    value: int | None
    unit: str

    @property
    def is_unlimited(self):
        return self.limit_type == PlanAllowance.LimitType.UNLIMITED

    @property
    def is_custom(self):
        return self.limit_type == PlanAllowance.LimitType.CUSTOM


def get_plan(code):
    try:
        return Plan.objects.get(code=code, is_active=True)
    except Plan.DoesNotExist as exc:
        raise PlanConfigurationError(f"Active billing plan '{code}' is not configured.") from exc


def get_default_plan():
    return get_plan("free")


def ensure_subscription(photographer):
    """Return the authoritative workspace subscription or provision Free.

    Query the subscription table directly rather than relying on Django's
    reverse one-to-one cache so entitlement and allowance checks always use the
    latest server-side plan assignment.
    """
    subscription = (
        Subscription.objects.select_related("plan")
        .filter(photographer=photographer)
        .first()
    )
    if subscription is not None:
        return subscription

    free_plan = get_default_plan()
    subscription, _ = Subscription.objects.get_or_create(
        photographer=photographer,
        defaults={
            "plan": free_plan,
            "status": Subscription.Status.ACTIVE,
            "billing_interval": Subscription.BillingInterval.FREE,
            "provider": Subscription.Provider.NONE,
        },
    )
    return Subscription.objects.select_related("plan").get(pk=subscription.pk)


def select_plan(photographer, plan_code, *, enforce_customer_selectable=True):
    """Assign a configured plan using a locked subscription row.

    Customer-initiated changes must respect ``customer_selectable``. This keeps
    Pro, Studio, and Enterprise configured but unavailable until explicitly
    enabled later. Internal/admin workflows may opt out when a future managed
    migration or sales-assisted Enterprise flow needs to assign a plan.
    """
    with transaction.atomic():
        plan = Plan.objects.select_for_update().get(code=plan_code, is_active=True)
        if enforce_customer_selectable and not plan.customer_selectable:
            raise PlanUnavailableError(f"The {plan.name} plan is not available for selection yet.")

        subscription = Subscription.objects.select_for_update().filter(photographer=photographer).first()
        if subscription is None:
            subscription = Subscription(photographer=photographer, plan=plan)

        subscription.plan = plan
        subscription.status = Subscription.Status.ACTIVE
        subscription.provider = Subscription.Provider.NONE
        subscription.provider_customer_id = ""
        subscription.provider_subscription_id = ""
        subscription.current_period_start = None
        subscription.current_period_end = None
        subscription.cancel_at_period_end = False
        subscription.ended_at = None
        subscription.billing_interval = (
            Subscription.BillingInterval.FREE if plan.code == "free" else Subscription.BillingInterval.CUSTOM
        )
        subscription.save()
        return subscription


def has_entitlement(photographer, code):
    subscription = ensure_subscription(photographer)
    return subscription.plan.entitlements.filter(code=code, enabled=True).exists()


def get_allowance(photographer, key):
    subscription = ensure_subscription(photographer)
    try:
        allowance = subscription.plan.allowances.get(key=key)
    except PlanAllowance.DoesNotExist as exc:
        raise PlanConfigurationError(
            f"Allowance '{key}' is not configured for plan '{subscription.plan.code}'."
        ) from exc
    return AllowanceValue(
        key=allowance.key,
        limit_type=allowance.limit_type,
        value=allowance.value,
        unit=allowance.unit,
    )
