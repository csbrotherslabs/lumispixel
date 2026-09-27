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


class AIOperation(models.Model):
    """Server-owned AI operation definition used to classify ledger activity."""

    code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    default_units = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "pk"]

    def __str__(self):
        return self.name


class AIUsageAccount(models.Model):
    """Long-lived AI balance container for one photographer workspace."""

    photographer = models.OneToOneField(
        "accounts.PhotographerProfile",
        on_delete=models.CASCADE,
        related_name="ai_usage_account",
    )
    purchased_balance = models.PositiveBigIntegerField(
        default=0,
        help_text="Persistent purchased AI units. Phase 6 will add funded top-ups to this balance.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.photographer} — AI usage"


class AIUsagePeriod(models.Model):
    """Calendar-month snapshot of the plan's included AI allowance."""

    account = models.ForeignKey(AIUsageAccount, on_delete=models.CASCADE, related_name="periods")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    included_allowance = models.PositiveBigIntegerField(blank=True, null=True)
    allowance_limit_type = models.CharField(
        max_length=12,
        choices=PlanAllowance.LimitType.choices,
        default=PlanAllowance.LimitType.NUMERIC,
    )
    included_consumed = models.PositiveBigIntegerField(default=0)
    included_reserved = models.PositiveBigIntegerField(default=0)
    purchased_reserved = models.PositiveBigIntegerField(default=0)
    plan_code_snapshot = models.SlugField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-starts_at"]
        constraints = [
            models.UniqueConstraint(fields=["account", "starts_at"], name="ai_period_acct_start_uq")
        ]
        indexes = [
            models.Index(fields=["account", "starts_at", "ends_at"], name="ai_period_lookup_idx")
        ]

    @property
    def included_remaining(self):
        if self.allowance_limit_type == PlanAllowance.LimitType.UNLIMITED:
            return None
        if self.included_allowance is None:
            return None
        return max(self.included_allowance - self.included_consumed - self.included_reserved, 0)

    def __str__(self):
        return f"{self.account.photographer} — {self.starts_at:%Y-%m}"


class AIUsageTransaction(models.Model):
    """Append-only AI accounting event."""

    class Kind(models.TextChoices):
        RESERVE = "reserve", "Reserve"
        SETTLE = "settle", "Settle"
        RELEASE = "release", "Release"
        REVERSE = "reverse", "Reverse"
        PURCHASE_GRANT = "purchase_grant", "Purchase grant"
        ADJUSTMENT = "adjustment", "Adjustment"

    account = models.ForeignKey(AIUsageAccount, on_delete=models.PROTECT, related_name="transactions")
    period = models.ForeignKey(
        AIUsagePeriod,
        on_delete=models.PROTECT,
        related_name="transactions",
        blank=True,
        null=True,
    )
    operation = models.ForeignKey(
        AIOperation,
        on_delete=models.PROTECT,
        related_name="transactions",
        blank=True,
        null=True,
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    included_units = models.PositiveBigIntegerField(default=0)
    purchased_units = models.PositiveBigIntegerField(default=0)
    related_transaction = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="follow_up_transactions",
        blank=True,
        null=True,
    )
    idempotency_key = models.CharField(max_length=160, unique=True)
    source_reference = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["account", "created_at"], name="ai_tx_acct_time_idx"),
            models.Index(fields=["kind", "created_at"], name="ai_tx_kind_time_idx"),
            models.Index(fields=["source_reference"], name="ai_tx_source_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(included_units__gt=0) | models.Q(purchased_units__gt=0),
                name="ai_tx_nonzero_ck",
            )
        ]

    @property
    def total_units(self):
        return self.included_units + self.purchased_units

    def __str__(self):
        return f"{self.account.photographer} — {self.kind} — {self.total_units}"
