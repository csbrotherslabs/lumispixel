from django.test import TestCase

from apps.accounts.models import PhotographerProfile, User

from .models import Plan, PlanAllowance, PlanPrice, Subscription
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
