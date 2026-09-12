from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Plan(models.Model):
    """LumisPixel-owned commercial plan definition and launch availability."""

    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)
    customer_selectable = models.BooleanField(
        default=False,
        help_text="Whether a photographer may self-select this plan. Paid plans stay disabled until launch readiness.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "pk"]

    def __str__(self):
        return self.name


class PlanPrice(models.Model):
    class BillingInterval(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        ANNUAL = "annual", "Annual"
        CUSTOM = "custom", "Custom"

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="prices")
    billing_interval = models.CharField(max_length=12, choices=BillingInterval.choices)
    amount_cents = models.PositiveIntegerField(blank=True, null=True)
    currency = models.CharField(max_length=3, default="USD")
    is_active = models.BooleanField(default=True)
    checkout_enabled = models.BooleanField(
        default=False,
        help_text="Keep disabled until a payment provider and checkout flow are ready.",
    )
    provider_product_id = models.CharField(max_length=255, blank=True)
    provider_price_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["plan__sort_order", "billing_interval"]
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "billing_interval", "currency"],
                name="billing_plan_interval_currency_unique",
            )
        ]

    def clean(self):
        if self.billing_interval == self.BillingInterval.CUSTOM and self.amount_cents is not None:
            raise ValidationError({"amount_cents": "Custom prices should not define a fixed amount."})
        if self.billing_interval != self.BillingInterval.CUSTOM and self.amount_cents is None:
            raise ValidationError({"amount_cents": "Monthly and annual prices require an amount."})

    def __str__(self):
        if self.amount_cents is None:
            return f"{self.plan.name} — Custom"
        return f"{self.plan.name} — {self.get_billing_interval_display()} ({self.currency} {self.amount_cents / 100:.2f})"


class PlanAllowance(models.Model):
    class LimitType(models.TextChoices):
        NUMERIC = "numeric", "Numeric"
        UNLIMITED = "unlimited", "Unlimited"
        CUSTOM = "custom", "Custom"

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="allowances")
    key = models.SlugField(max_length=80)
    label = models.CharField(max_length=120)
    limit_type = models.CharField(max_length=12, choices=LimitType.choices, default=LimitType.NUMERIC)
    value = models.PositiveBigIntegerField(blank=True, null=True)
    unit = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["plan__sort_order", "key"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "key"], name="billing_plan_allowance_unique")
        ]

    def clean(self):
        if self.limit_type == self.LimitType.NUMERIC and self.value is None:
            raise ValidationError({"value": "Numeric allowances require a value."})
        if self.limit_type != self.LimitType.NUMERIC and self.value is not None:
            raise ValidationError({"value": "Unlimited and custom allowances should not define a numeric value."})

    def __str__(self):
        return f"{self.plan.name} — {self.label}"


class PlanEntitlement(models.Model):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="entitlements")
    code = models.SlugField(max_length=100)
    label = models.CharField(max_length=140)
    enabled = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["plan__sort_order", "code"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "code"], name="billing_plan_entitlement_unique")
        ]

    def __str__(self):
        return f"{self.plan.name} — {self.label}"


class Subscription(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        PAST_DUE = "past_due", "Past due"
        CANCELED = "canceled", "Canceled"
        INCOMPLETE = "incomplete", "Incomplete"

    class BillingInterval(models.TextChoices):
        FREE = "free", "Free"
        MONTHLY = "monthly", "Monthly"
        ANNUAL = "annual", "Annual"
        CUSTOM = "custom", "Custom"

    class Provider(models.TextChoices):
        NONE = "none", "None"
        STRIPE = "stripe", "Stripe"

    photographer = models.OneToOneField(
        "accounts.PhotographerProfile",
        on_delete=models.CASCADE,
        related_name="billing_subscription",
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    billing_interval = models.CharField(max_length=12, choices=BillingInterval.choices, default=BillingInterval.FREE)
    provider = models.CharField(max_length=12, choices=Provider.choices, default=Provider.NONE)
    provider_customer_id = models.CharField(max_length=255, blank=True)
    provider_subscription_id = models.CharField(max_length=255, blank=True)
    current_period_start = models.DateTimeField(blank=True, null=True)
    current_period_end = models.DateTimeField(blank=True, null=True)
    cancel_at_period_end = models.BooleanField(default=False)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["plan", "status"], name="billing_sub_plan_status"),
            models.Index(fields=["provider", "provider_subscription_id"], name="billing_sub_provider_id"),
        ]

    def __str__(self):
        return f"{self.photographer} — {self.plan.name}"
