from datetime import datetime

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User

from .ai_usage import (
    AIUsageLimitExceeded,
    AIUsageReservationError,
    get_usage_balance,
    release_ai_usage,
    reserve_ai_usage,
    reverse_ai_usage,
    settle_ai_usage,
)
from .models import (
    AIOperation,
    AIUsageAccount,
    AIUsagePeriod,
    AIUsageTransaction,
    Plan,
    PlanAllowance,
    PlanPrice,
    Subscription,
)
from .services import PlanUnavailableError, get_allowance, has_entitlement, select_plan


class BillingCatalogTests(TestCase):
    def test_launch_catalog_contains_all_four_plans(self):
        self.assertEqual(
            list(Plan.objects.order_by("sort_order").values_list("code", flat=True)),
            ["free", "pro", "studio", "enterprise"],
        )

    def test_only_free_is_customer_selectable_at_launch(self):
        selectable = list(
            Plan.objects.filter(is_active=True, customer_selectable=True).values_list("code", flat=True)
        )
        self.assertEqual(selectable, ["free"])

    def test_paid_prices_are_configured_but_checkout_is_disabled(self):
        pro = Plan.objects.get(code="pro")
        studio = Plan.objects.get(code="studio")
        self.assertEqual(
            set(pro.prices.values_list("billing_interval", "amount_cents")),
            {("monthly", 2900), ("annual", 27600)},
        )
        self.assertEqual(
            set(studio.prices.values_list("billing_interval", "amount_cents")),
            {("monthly", 5900), ("annual", 56400)},
        )
        self.assertFalse(PlanPrice.objects.exclude(plan__code="free").filter(checkout_enabled=True).exists())

    def test_launch_allowances_match_pricing_architecture(self):
        expected = {
            "free": (5 * 1024**3, 100, 1),
            "pro": (250 * 1024**3, 2000, 1),
            "studio": (1024 * 1024**3, 7500, 3),
        }
        for plan_code, (storage_bytes, ai_actions, team_members) in expected.items():
            plan = Plan.objects.get(code=plan_code)
            self.assertEqual(plan.allowances.get(key="storage_bytes").value, storage_bytes)
            self.assertEqual(plan.allowances.get(key="ai_monthly_actions").value, ai_actions)
            self.assertEqual(plan.allowances.get(key="team_members").value, team_members)

        enterprise = Plan.objects.get(code="enterprise")
        self.assertEqual(
            enterprise.allowances.get(key="ai_monthly_actions").limit_type,
            PlanAllowance.LimitType.CUSTOM,
        )

    def test_higher_plans_include_lower_plan_entitlements(self):
        self.assertTrue(Plan.objects.get(code="pro").entitlements.filter(code="password_protected_galleries").exists())
        self.assertTrue(Plan.objects.get(code="studio").entitlements.filter(code="custom_domain").exists())
        self.assertTrue(Plan.objects.get(code="enterprise").entitlements.filter(code="advanced_workflow_automation").exists())


class SubscriptionFoundationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="billing-owner@example.com",
            password="strong-test-password",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
        )
        self.photographer = PhotographerProfile.objects.create(
            user=self.user,
            display_name="Billing Test Studio",
        )

    def test_new_photographer_is_provisioned_on_free_plan(self):
        subscription = self.photographer.billing_subscription
        self.assertEqual(subscription.plan.code, "free")
        self.assertEqual(subscription.status, Subscription.Status.ACTIVE)
        self.assertEqual(subscription.billing_interval, Subscription.BillingInterval.FREE)
        self.assertEqual(subscription.provider, Subscription.Provider.NONE)

    def test_customer_cannot_select_paid_plan_before_launch_gate_opens(self):
        for plan_code in ("pro", "studio", "enterprise"):
            with self.assertRaises(PlanUnavailableError):
                select_plan(self.photographer, plan_code)
        self.photographer.billing_subscription.refresh_from_db()
        self.assertEqual(self.photographer.billing_subscription.plan.code, "free")

    def test_free_plan_can_be_selected_idempotently(self):
        first = select_plan(self.photographer, "free")
        second = select_plan(self.photographer, "free")
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Subscription.objects.filter(photographer=self.photographer).count(), 1)

    def test_internal_assignment_can_support_future_managed_plan_changes(self):
        subscription = select_plan(
            self.photographer,
            "pro",
            enforce_customer_selectable=False,
        )
        self.assertEqual(subscription.plan.code, "pro")
        self.assertEqual(subscription.provider, Subscription.Provider.NONE)
        self.assertEqual(subscription.billing_interval, Subscription.BillingInterval.CUSTOM)

    def test_entitlement_and_allowance_services_use_server_side_plan_data(self):
        self.assertTrue(has_entitlement(self.photographer, "password_protected_galleries"))
        self.assertFalse(has_entitlement(self.photographer, "custom_domain"))

        allowance = get_allowance(self.photographer, "ai_monthly_actions")
        self.assertEqual(allowance.value, 100)
        self.assertEqual(allowance.unit, "actions")
        self.assertFalse(allowance.is_unlimited)

        select_plan(self.photographer, "pro", enforce_customer_selectable=False)
        self.assertTrue(has_entitlement(self.photographer, "custom_domain"))
        self.assertEqual(get_allowance(self.photographer, "ai_monthly_actions").value, 2000)


class AIUsageLedgerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="ai-ledger@example.com",
            password="strong-test-password",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
        )
        self.photographer = PhotographerProfile.objects.create(
            user=self.user,
            display_name="AI Ledger Studio",
        )
        self.operation = AIOperation.objects.create(
            code="test-edit",
            name="Test Edit",
            default_units=1,
        )

    def test_current_period_snapshots_free_monthly_allowance(self):
        balance = get_usage_balance(self.photographer)
        self.assertEqual(balance.included_allowance, 100)
        self.assertEqual(balance.included_consumed, 0)
        self.assertEqual(balance.included_remaining, 100)
        self.assertEqual(balance.purchased_balance, 0)
        period = AIUsagePeriod.objects.get(account__photographer=self.photographer)
        self.assertEqual(period.plan_code_snapshot, "free")

    def test_reserve_then_settle_consumes_included_units(self):
        reservation = reserve_ai_usage(
            self.photographer,
            self.operation.code,
            units=4,
            idempotency_key="reserve-1",
            source_reference="image:123",
        )
        self.assertEqual(reservation.kind, AIUsageTransaction.Kind.RESERVE)
        self.assertEqual(reservation.included_units, 4)
        self.assertEqual(get_usage_balance(self.photographer).included_reserved, 4)

        settlement = settle_ai_usage(reservation, idempotency_key="settle-1")
        self.assertEqual(settlement.kind, AIUsageTransaction.Kind.SETTLE)
        balance = get_usage_balance(self.photographer)
        self.assertEqual(balance.included_reserved, 0)
        self.assertEqual(balance.included_consumed, 4)
        self.assertEqual(balance.included_remaining, 96)

    def test_partial_settlement_automatically_releases_unused_units(self):
        reservation = reserve_ai_usage(
            self.photographer,
            self.operation.code,
            units=5,
            idempotency_key="reserve-partial",
        )
        settlement = settle_ai_usage(
            reservation,
            idempotency_key="settle-partial",
            actual_units=2,
        )
        self.assertEqual(settlement.included_units, 2)
        self.assertTrue(
            reservation.follow_up_transactions.filter(
                kind=AIUsageTransaction.Kind.RELEASE,
                included_units=3,
            ).exists()
        )
        balance = get_usage_balance(self.photographer)
        self.assertEqual(balance.included_consumed, 2)
        self.assertEqual(balance.included_reserved, 0)

    def test_release_after_failure_restores_available_allowance(self):
        reservation = reserve_ai_usage(
            self.photographer,
            self.operation.code,
            units=7,
            idempotency_key="reserve-failed",
        )
        released = release_ai_usage(reservation, idempotency_key="release-failed")
        self.assertEqual(released.kind, AIUsageTransaction.Kind.RELEASE)
        balance = get_usage_balance(self.photographer)
        self.assertEqual(balance.included_consumed, 0)
        self.assertEqual(balance.included_reserved, 0)
        self.assertEqual(balance.included_remaining, 100)

    def test_settlement_can_be_reversed_without_mutating_history(self):
        reservation = reserve_ai_usage(
            self.photographer,
            self.operation.code,
            units=3,
            idempotency_key="reserve-reverse",
        )
        settlement = settle_ai_usage(reservation, idempotency_key="settle-reverse")
        reversal = reverse_ai_usage(settlement, idempotency_key="reverse-1")
        self.assertEqual(reversal.kind, AIUsageTransaction.Kind.REVERSE)
        self.assertEqual(get_usage_balance(self.photographer).included_consumed, 0)
        self.assertEqual(AIUsageTransaction.objects.count(), 3)

    def test_duplicate_idempotency_key_does_not_double_reserve(self):
        first = reserve_ai_usage(
            self.photographer,
            self.operation.code,
            units=6,
            idempotency_key="same-request",
        )
        second = reserve_ai_usage(
            self.photographer,
            self.operation.code,
            units=6,
            idempotency_key="same-request",
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(AIUsageTransaction.objects.filter(kind=AIUsageTransaction.Kind.RESERVE).count(), 1)
        self.assertEqual(get_usage_balance(self.photographer).included_reserved, 6)

    def test_reservation_rejects_usage_beyond_available_balance(self):
        with self.assertRaises(AIUsageLimitExceeded):
            reserve_ai_usage(
                self.photographer,
                self.operation.code,
                units=101,
                idempotency_key="too-many",
            )
        self.assertFalse(AIUsageTransaction.objects.filter(idempotency_key="too-many").exists())

    def test_purchased_balance_is_reserved_after_included_allowance(self):
        account = AIUsageAccount.objects.create(photographer=self.photographer, purchased_balance=10)
        reservation = reserve_ai_usage(
            self.photographer,
            self.operation.code,
            units=105,
            idempotency_key="reserve-purchased",
        )
        self.assertEqual(reservation.included_units, 100)
        self.assertEqual(reservation.purchased_units, 5)
        settlement = settle_ai_usage(reservation, idempotency_key="settle-purchased")
        account.refresh_from_db()
        self.assertEqual(settlement.purchased_units, 5)
        self.assertEqual(account.purchased_balance, 5)

    def test_monthly_included_allowance_resets_in_new_calendar_month(self):
        tz = timezone.get_current_timezone()
        september = timezone.make_aware(datetime(2026, 9, 15, 12, 0), tz)
        october = timezone.make_aware(datetime(2026, 10, 1, 12, 0), tz)
        reservation = reserve_ai_usage(
            self.photographer,
            self.operation.code,
            units=20,
            idempotency_key="sept-reserve",
            moment=september,
        )
        settle_ai_usage(reservation, idempotency_key="sept-settle")
        september_balance = get_usage_balance(self.photographer, moment=september)
        october_balance = get_usage_balance(self.photographer, moment=october)
        self.assertEqual(september_balance.included_remaining, 80)
        self.assertEqual(october_balance.included_remaining, 100)
        self.assertEqual(AIUsagePeriod.objects.filter(account__photographer=self.photographer).count(), 2)

    def test_fully_resolved_reservation_cannot_be_released_again(self):
        reservation = reserve_ai_usage(
            self.photographer,
            self.operation.code,
            units=2,
            idempotency_key="resolved-reserve",
        )
        settle_ai_usage(reservation, idempotency_key="resolved-settle")
        with self.assertRaises(AIUsageReservationError):
            release_ai_usage(reservation, idempotency_key="resolved-release")
