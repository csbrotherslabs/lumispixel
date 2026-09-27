from django.test import TestCase

from apps.accounts.models import PhotographerProfile, User
from apps.billing.ai_usage import get_or_create_usage_account, reserve_ai_usage, settle_ai_usage
from apps.billing.models import AIOperation, AIUsagePeriod
from apps.billing.services import select_plan
from apps.dashboard.ai_wallet import build_ai_wallet


class AIWalletWorkspaceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="ai-wallet@example.com",
            password="strong-test-password",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
        )
        self.photographer = PhotographerProfile.objects.create(
            user=self.user,
            display_name="AI Wallet Studio",
            onboarding_completed=True,
        )
        self.operation = AIOperation.objects.create(
            code="wallet-test",
            name="Wallet test operation",
            default_units=1,
        )

    def test_free_wallet_uses_plan_allowance(self):
        wallet = build_ai_wallet(self.photographer)

        self.assertEqual(wallet["plan_code"], "free")
        self.assertEqual(wallet["included_allowance"], 100)
        self.assertEqual(wallet["included_consumed"], 0)
        self.assertEqual(wallet["included_remaining"], 100)
        self.assertEqual(wallet["total_available"], 100)
        self.assertEqual(wallet["used_percent"], 0)
        self.assertIsNotNone(wallet["reset_date"])

    def test_wallet_reflects_pending_and_settled_usage(self):
        reservation = reserve_ai_usage(
            self.photographer,
            self.operation.code,
            units=12,
            idempotency_key="wallet-pending",
        )
        pending = build_ai_wallet(self.photographer)
        self.assertEqual(pending["included_reserved"], 12)
        self.assertEqual(pending["included_remaining"], 88)
        self.assertEqual(pending["total_available"], 88)

        settle_ai_usage(reservation, idempotency_key="wallet-settle", actual_units=7)
        settled = build_ai_wallet(self.photographer)
        self.assertEqual(settled["included_consumed"], 7)
        self.assertEqual(settled["included_reserved"], 0)
        self.assertEqual(settled["included_remaining"], 93)
        self.assertEqual(settled["total_available"], 93)
        self.assertEqual(settled["used_percent"], 7)

    def test_wallet_includes_persistent_extra_credits(self):
        account = get_or_create_usage_account(self.photographer)
        account.purchased_balance = 250
        account.save(update_fields=["purchased_balance", "updated_at"])

        wallet = build_ai_wallet(self.photographer)
        self.assertEqual(wallet["purchased_available"], 250)
        self.assertEqual(wallet["total_available"], 350)

    def test_custom_plan_is_displayed_without_creating_numeric_period(self):
        select_plan(self.photographer, "enterprise", enforce_customer_selectable=False)

        wallet = build_ai_wallet(self.photographer)
        self.assertEqual(wallet["plan_code"], "enterprise")
        self.assertTrue(wallet["is_custom"])
        self.assertIsNone(wallet["included_allowance"])
        self.assertFalse(AIUsagePeriod.objects.filter(account__photographer=self.photographer).exists())

    def test_dashboard_renders_read_only_ai_wallet_without_checkout(self):
        self.client.force_login(self.user)
        response = self.client.get("/photographer/workspace/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AI Wallet")
        self.assertContains(response, "100 included / month")
        self.assertNotContains(response, "Buy credits")
        self.assertNotContains(response, "Checkout")
