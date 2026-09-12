from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import PhotographerProfile, User
from apps.billing.ai_usage import reserve_ai_usage, settle_ai_usage
from apps.billing.models import AIOperation, Plan, Subscription
from apps.galleries.models import Gallery


class BillingAccountWorkspaceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="billing-account@example.com",
            password="strong-test-password",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
        )
        self.photographer = PhotographerProfile.objects.create(
            user=self.user,
            display_name="Billing Account Studio",
            onboarding_completed=True,
        )
        self.client.force_login(self.user)
        self.url = reverse("photographer_workspace:billing")

    def test_billing_page_replaces_placeholder_and_shows_current_free_plan(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "photographer_workspace/billing/account.html")
        self.assertContains(response, "Billing &amp; Plan")
        self.assertContains(response, "Current plan")
        self.assertContains(response, "Free")
        self.assertContains(response, "5 GB plan allowance")
        self.assertContains(response, "100")
        self.assertContains(response, "included actions remaining")
        self.assertNotContains(response, "Planned capabilities")

    def test_billing_page_uses_actual_gallery_storage(self):
        Gallery.objects.create(
            photographer=self.photographer,
            name="Storage Gallery",
            slug="storage-gallery",
            storage_used=2 * 1024 ** 3,
        )

        response = self.client.get(self.url)

        self.assertContains(response, "2 GB")
        self.assertContains(response, "5 GB plan allowance")
        self.assertContains(response, "3 GB remaining")
        self.assertContains(response, "40% used")

    def test_billing_page_reads_live_ai_wallet_balance(self):
        operation = AIOperation.objects.create(code="billing-test", name="Billing Test")
        reservation = reserve_ai_usage(
            self.photographer,
            operation.code,
            units=12,
            idempotency_key="billing-account-reserve",
        )
        settle_ai_usage(
            reservation,
            actual_units=7,
            idempotency_key="billing-account-settle",
        )

        response = self.client.get(self.url)

        self.assertContains(response, ">93<")
        self.assertContains(response, ">7<")
        self.assertContains(response, "Extra credits")

    def test_paid_plans_are_visible_but_cannot_be_selected_during_launch_gate(self):
        response = self.client.get(self.url)

        self.assertContains(response, "Pro")
        self.assertContains(response, "Studio")
        self.assertContains(response, "Enterprise")
        self.assertContains(response, "Coming soon", count=2)
        self.assertContains(response, "Contact Sales")

        response = self.client.post(self.url, {"plan": "pro"}, follow=True)
        self.assertEqual(response.status_code, 200)
        subscription = Subscription.objects.get(photographer=self.photographer)
        self.assertEqual(subscription.plan.code, "free")
        self.assertContains(response, "The Pro plan is not available for selection yet.")

    def test_customer_selectable_plan_change_endpoint_is_future_safe(self):
        pro = Plan.objects.get(code="pro")
        pro.customer_selectable = True
        pro.save(update_fields=["customer_selectable", "updated_at"])

        response = self.client.post(self.url, {"plan": "pro"}, follow=True)

        self.assertEqual(response.status_code, 200)
        subscription = Subscription.objects.get(photographer=self.photographer)
        self.assertEqual(subscription.plan.code, "pro")
        self.assertContains(response, "Your workspace is now on the Pro plan.")

    def test_billing_page_requires_authentication(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)
