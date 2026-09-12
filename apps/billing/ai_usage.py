from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, time

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import (
    AIOperation,
    AIUsageAccount,
    AIUsagePeriod,
    AIUsageTransaction,
    PlanAllowance,
)
from .services import PlanConfigurationError, ensure_subscription, get_allowance


class AIUsageError(RuntimeError):
    """Base error for AI usage accounting failures."""


class AIUsageLimitExceeded(AIUsageError):
    """Raised when a reservation would exceed available AI units."""


class AIUsageReservationError(AIUsageError):
    """Raised when a reservation cannot be settled, released, or reversed."""


@dataclass(frozen=True)
class AIUsageBalance:
    included_allowance: int | None
    included_consumed: int
    included_reserved: int
    included_remaining: int | None
    purchased_balance: int
    purchased_reserved: int
    purchased_available: int
    allowance_limit_type: str
    period_starts_at: datetime
    period_ends_at: datetime


def _month_bounds(moment=None):
    moment = timezone.localtime(moment or timezone.now())
    tz = timezone.get_current_timezone()
    starts_at = timezone.make_aware(datetime.combine(moment.date().replace(day=1), time.min), tz)
    last_day = monthrange(moment.year, moment.month)[1]
    ends_at = timezone.make_aware(
        datetime.combine(moment.date().replace(day=last_day), time.max),
        tz,
    )
    return starts_at, ends_at


def get_or_create_usage_account(photographer):
    account, _ = AIUsageAccount.objects.get_or_create(photographer=photographer)
    return account


def _allowance_snapshot(photographer):
    subscription = ensure_subscription(photographer)
    allowance = get_allowance(photographer, "ai_monthly_actions")
    if allowance.is_custom:
        raise PlanConfigurationError(
            f"Plan '{subscription.plan.code}' has a custom AI allowance and requires a configured numeric or unlimited limit before AI processing."
        )
    return subscription.plan.code, allowance.limit_type, allowance.value


def get_or_create_usage_period(photographer, *, moment=None, lock=False):
    starts_at, ends_at = _month_bounds(moment)
    account = get_or_create_usage_account(photographer)
    queryset = AIUsagePeriod.objects
    if lock:
        queryset = queryset.select_for_update()
    period = queryset.filter(account=account, starts_at=starts_at).first()
    if period is not None:
        return period

    plan_code, limit_type, allowance_value = _allowance_snapshot(photographer)
    period, _ = AIUsagePeriod.objects.get_or_create(
        account=account,
        starts_at=starts_at,
        defaults={
            "ends_at": ends_at,
            "included_allowance": allowance_value,
            "allowance_limit_type": limit_type,
            "plan_code_snapshot": plan_code,
        },
    )
    if lock:
        period = AIUsagePeriod.objects.select_for_update().get(pk=period.pk)
    return period


def get_usage_balance(photographer, *, moment=None):
    account = get_or_create_usage_account(photographer)
    period = get_or_create_usage_period(photographer, moment=moment)
    included_remaining = period.included_remaining
    purchased_available = max(account.purchased_balance - period.purchased_reserved, 0)
    return AIUsageBalance(
        included_allowance=period.included_allowance,
        included_consumed=period.included_consumed,
        included_reserved=period.included_reserved,
        included_remaining=included_remaining,
        purchased_balance=account.purchased_balance,
        purchased_reserved=period.purchased_reserved,
        purchased_available=purchased_available,
        allowance_limit_type=period.allowance_limit_type,
        period_starts_at=period.starts_at,
        period_ends_at=period.ends_at,
    )


def _get_operation(operation_code):
    try:
        return AIOperation.objects.get(code=operation_code, is_active=True)
    except AIOperation.DoesNotExist as exc:
        raise PlanConfigurationError(f"Active AI operation '{operation_code}' is not configured.") from exc


def reserve_ai_usage(
    photographer,
    operation_code,
    *,
    units=None,
    idempotency_key,
    source_reference="",
    metadata=None,
    moment=None,
):
    """Reserve AI units before external processing begins.

    Included monthly allowance is consumed first. Persistent purchased units are
    reserved only after included units are exhausted. Reusing an idempotency key
    returns the original transaction without double-reserving.
    """
    existing = AIUsageTransaction.objects.filter(idempotency_key=idempotency_key).first()
    if existing is not None:
        return existing

    operation = _get_operation(operation_code)
    units = operation.default_units if units is None else int(units)
    if units <= 0:
        raise ValueError("AI usage reservation units must be greater than zero.")

    with transaction.atomic():
        existing = AIUsageTransaction.objects.select_for_update().filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            return existing

        account = AIUsageAccount.objects.select_for_update().filter(photographer=photographer).first()
        if account is None:
            account = AIUsageAccount.objects.create(photographer=photographer)
            account = AIUsageAccount.objects.select_for_update().get(pk=account.pk)

        period = get_or_create_usage_period(photographer, moment=moment, lock=True)

        if period.allowance_limit_type == PlanAllowance.LimitType.UNLIMITED:
            included_units = units
            purchased_units = 0
        else:
            included_available = period.included_remaining or 0
            included_units = min(units, included_available)
            remainder = units - included_units
            purchased_available = max(account.purchased_balance - period.purchased_reserved, 0)
            purchased_units = min(remainder, purchased_available)
            if included_units + purchased_units < units:
                raise AIUsageLimitExceeded(
                    f"AI usage limit exceeded: requested {units} units, "
                    f"but only {included_available + purchased_available} are available."
                )

        period.included_reserved += included_units
        period.purchased_reserved += purchased_units
        period.save(update_fields=["included_reserved", "purchased_reserved", "updated_at"])

        return AIUsageTransaction.objects.create(
            account=account,
            period=period,
            operation=operation,
            kind=AIUsageTransaction.Kind.RESERVE,
            included_units=included_units,
            purchased_units=purchased_units,
            idempotency_key=idempotency_key,
            source_reference=source_reference,
            metadata=metadata or {},
        )


def _reservation_remaining(reservation):
    totals = reservation.follow_up_transactions.filter(
        kind__in=[AIUsageTransaction.Kind.SETTLE, AIUsageTransaction.Kind.RELEASE]
    ).aggregate(
        included=Sum("included_units"),
        purchased=Sum("purchased_units"),
    )
    return (
        reservation.included_units - (totals["included"] or 0),
        reservation.purchased_units - (totals["purchased"] or 0),
    )


def settle_ai_usage(reservation, *, idempotency_key, actual_units=None, metadata=None):
    """Settle all or part of a reservation and release any unused remainder."""
    existing = AIUsageTransaction.objects.filter(idempotency_key=idempotency_key).first()
    if existing is not None:
        return existing

    reservation_id = reservation.pk if isinstance(reservation, AIUsageTransaction) else reservation
    with transaction.atomic():
        existing = AIUsageTransaction.objects.select_for_update().filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            return existing

        reservation = AIUsageTransaction.objects.select_for_update().select_related("account", "period").get(pk=reservation_id)
        if reservation.kind != AIUsageTransaction.Kind.RESERVE or reservation.period_id is None:
            raise AIUsageReservationError("Only reservation transactions can be settled.")

        account = AIUsageAccount.objects.select_for_update().get(pk=reservation.account_id)
        period = AIUsagePeriod.objects.select_for_update().get(pk=reservation.period_id)
        remaining_included, remaining_purchased = _reservation_remaining(reservation)
        remaining_total = remaining_included + remaining_purchased
        if remaining_total <= 0:
            raise AIUsageReservationError("This reservation has already been fully resolved.")

        actual_units = remaining_total if actual_units is None else int(actual_units)
        if actual_units < 0 or actual_units > remaining_total:
            raise AIUsageReservationError("Settlement units must be between zero and the unresolved reservation amount.")

        settle_included = min(actual_units, remaining_included)
        settle_purchased = actual_units - settle_included
        release_included = remaining_included - settle_included
        release_purchased = remaining_purchased - settle_purchased

        period.included_reserved -= remaining_included
        period.purchased_reserved -= remaining_purchased
        period.included_consumed += settle_included
        if settle_purchased > account.purchased_balance:
            raise AIUsageReservationError("Purchased AI balance is lower than the reserved settlement amount.")
        account.purchased_balance -= settle_purchased
        period.save(update_fields=["included_reserved", "purchased_reserved", "included_consumed", "updated_at"])
        account.save(update_fields=["purchased_balance", "updated_at"])

        if actual_units == 0:
            return AIUsageTransaction.objects.create(
                account=account,
                period=period,
                operation=reservation.operation,
                kind=AIUsageTransaction.Kind.RELEASE,
                included_units=release_included,
                purchased_units=release_purchased,
                related_transaction=reservation,
                idempotency_key=idempotency_key,
                source_reference=reservation.source_reference,
                metadata=metadata or {},
            )

        settled = AIUsageTransaction.objects.create(
            account=account,
            period=period,
            operation=reservation.operation,
            kind=AIUsageTransaction.Kind.SETTLE,
            included_units=settle_included,
            purchased_units=settle_purchased,
            related_transaction=reservation,
            idempotency_key=idempotency_key,
            source_reference=reservation.source_reference,
            metadata=metadata or {},
        )
        if release_included or release_purchased:
            AIUsageTransaction.objects.create(
                account=account,
                period=period,
                operation=reservation.operation,
                kind=AIUsageTransaction.Kind.RELEASE,
                included_units=release_included,
                purchased_units=release_purchased,
                related_transaction=reservation,
                idempotency_key=f"{idempotency_key}:release",
                source_reference=reservation.source_reference,
                metadata={"automatic": True},
            )
        return settled


def release_ai_usage(reservation, *, idempotency_key, metadata=None):
    """Release the unresolved portion of a reservation after failed/cancelled work."""
    existing = AIUsageTransaction.objects.filter(idempotency_key=idempotency_key).first()
    if existing is not None:
        return existing

    reservation_id = reservation.pk if isinstance(reservation, AIUsageTransaction) else reservation
    with transaction.atomic():
        existing = AIUsageTransaction.objects.select_for_update().filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            return existing

        reservation = AIUsageTransaction.objects.select_for_update().select_related("period").get(pk=reservation_id)
        if reservation.kind != AIUsageTransaction.Kind.RESERVE or reservation.period_id is None:
            raise AIUsageReservationError("Only reservation transactions can be released.")
        period = AIUsagePeriod.objects.select_for_update().get(pk=reservation.period_id)
        remaining_included, remaining_purchased = _reservation_remaining(reservation)
        if remaining_included + remaining_purchased <= 0:
            raise AIUsageReservationError("This reservation has already been fully resolved.")

        period.included_reserved -= remaining_included
        period.purchased_reserved -= remaining_purchased
        period.save(update_fields=["included_reserved", "purchased_reserved", "updated_at"])

        return AIUsageTransaction.objects.create(
            account=reservation.account,
            period=period,
            operation=reservation.operation,
            kind=AIUsageTransaction.Kind.RELEASE,
            included_units=remaining_included,
            purchased_units=remaining_purchased,
            related_transaction=reservation,
            idempotency_key=idempotency_key,
            source_reference=reservation.source_reference,
            metadata=metadata or {},
        )


def reverse_ai_usage(settlement, *, idempotency_key, metadata=None):
    """Append a reversal for a settled transaction and restore its balances."""
    existing = AIUsageTransaction.objects.filter(idempotency_key=idempotency_key).first()
    if existing is not None:
        return existing

    settlement_id = settlement.pk if isinstance(settlement, AIUsageTransaction) else settlement
    with transaction.atomic():
        existing = AIUsageTransaction.objects.select_for_update().filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            return existing

        settlement = AIUsageTransaction.objects.select_for_update().select_related("account", "period").get(pk=settlement_id)
        if settlement.kind != AIUsageTransaction.Kind.SETTLE or settlement.period_id is None:
            raise AIUsageReservationError("Only settled AI usage can be reversed.")
        if settlement.follow_up_transactions.filter(kind=AIUsageTransaction.Kind.REVERSE).exists():
            raise AIUsageReservationError("This settlement has already been reversed.")

        account = AIUsageAccount.objects.select_for_update().get(pk=settlement.account_id)
        period = AIUsagePeriod.objects.select_for_update().get(pk=settlement.period_id)
        if period.included_consumed < settlement.included_units:
            raise AIUsageReservationError("Included usage balance is inconsistent with the settlement being reversed.")

        period.included_consumed -= settlement.included_units
        account.purchased_balance += settlement.purchased_units
        period.save(update_fields=["included_consumed", "updated_at"])
        account.save(update_fields=["purchased_balance", "updated_at"])

        return AIUsageTransaction.objects.create(
            account=account,
            period=period,
            operation=settlement.operation,
            kind=AIUsageTransaction.Kind.REVERSE,
            included_units=settlement.included_units,
            purchased_units=settlement.purchased_units,
            related_transaction=settlement,
            idempotency_key=idempotency_key,
            source_reference=settlement.source_reference,
            metadata=metadata or {},
        )
