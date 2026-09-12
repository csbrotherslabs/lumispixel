from django.test import TestCase
from django.urls import reverse

from apps.billing.models import Plan, PlanAllowance, PlanPrice


class PricingMarketingSynchronizationTests(TestCase):
    def test_pricing_page_uses_billing_plan_catalog(self):
        response = self.client.get(reverse("core:pricing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Free")
        self.assertContains(response, "Pro")
        self.assertContains(response, "Studio")
        self.assertContains(response, "Enterprise")
        self.assertContains(response, "5 GB storage")
        self.assertContains(response, "100 AI image actions / month")
        self.assertContains(response, "$29 / month")
        self.assertContains(response, "$23 / month · billed annually at $276")

    def test_marketing_price_changes_when_plan_price_changes(self):
        pro = Plan.objects.get(code="pro")
        monthly = PlanPrice.objects.get(plan=pro, billing_interval=PlanPrice.BillingInterval.MONTHLY)
        monthly.amount_cents = 3100
        monthly.save(update_fields=["amount_cents", "updated_at"])

        response = self.client.get(reverse("core:pricing"))

        self.assertContains(response, "$31 / month")
        self.assertNotContains(response, 'data-monthly-copy="$29 / month"')

    def test_marketing_allowance_changes_when_plan_allowance_changes(self):
        free = Plan.objects.get(code="free")
        allowance = PlanAllowance.objects.get(plan=free, key="ai_monthly_actions")
        allowance.value = 125
        allowance.save(update_fields=["value", "updated_at"])

        response = self.client.get(reverse("core:pricing"))

        self.assertContains(response, "125 AI image actions / month")

    def test_paid_plans_remain_marketing_visible_but_not_selectable(self):
        response = self.client.get(reverse("core:pricing"))

        self.assertContains(response, "Paid upgrades are coming after AI launch readiness", count=3)
        self.assertContains(response, "Coming soon", count=2)
        self.assertContains(response, "Contact Sales")
        self.assertContains(response, "Start Free")
        self.assertNotContains(response, "Start Pro Free")
        self.assertNotContains(response, "Start Studio Free")

    def test_homepage_catalog_payload_comes_from_same_billing_records(self):
        response = self.client.get(reverse("core:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="marketing-pricing-data"')
        self.assertContains(response, '"code": "free"')
        self.assertContains(response, '"code": "pro"')
        self.assertContains(response, '"monthly": "$29 / month"')
        self.assertContains(response, '"available": false')
