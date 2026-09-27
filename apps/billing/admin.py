from django.contrib import admin

from .models import (
    AIOperation,
    AIUsageAccount,
    AIUsagePeriod,
    AIUsageTransaction,
    Plan,
    PlanAllowance,
    PlanEntitlement,
    PlanPrice,
    Subscription,
)


class PlanPriceInline(admin.TabularInline):
    model = PlanPrice
    extra = 0


class PlanAllowanceInline(admin.TabularInline):
    model = PlanAllowance
    extra = 0


class PlanEntitlementInline(admin.TabularInline):
    model = PlanEntitlement
    extra = 0


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "is_public", "customer_selectable", "sort_order")
    list_filter = ("is_active", "is_public", "customer_selectable")
    search_fields = ("name", "code")
    ordering = ("sort_order", "pk")
    inlines = (PlanPriceInline, PlanAllowanceInline, PlanEntitlementInline)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("photographer", "plan", "status", "billing_interval", "provider", "updated_at")
    list_filter = ("plan", "status", "billing_interval", "provider")
    search_fields = (
        "photographer__display_name",
        "photographer__business_name",
        "photographer__user__email",
        "provider_customer_id",
        "provider_subscription_id",
    )
    autocomplete_fields = ("photographer", "plan")
    readonly_fields = ("created_at", "updated_at")


@admin.register(PlanPrice)
class PlanPriceAdmin(admin.ModelAdmin):
    list_display = ("plan", "billing_interval", "currency", "amount_cents", "is_active", "checkout_enabled")
    list_filter = ("billing_interval", "currency", "is_active", "checkout_enabled")
    search_fields = ("plan__name", "provider_product_id", "provider_price_id")


@admin.register(PlanAllowance)
class PlanAllowanceAdmin(admin.ModelAdmin):
    list_display = ("plan", "key", "label", "limit_type", "value", "unit")
    list_filter = ("plan", "limit_type")
    search_fields = ("key", "label", "plan__name")


@admin.register(PlanEntitlement)
class PlanEntitlementAdmin(admin.ModelAdmin):
    list_display = ("plan", "code", "label", "enabled")
    list_filter = ("plan", "enabled")
    search_fields = ("code", "label", "plan__name")


@admin.register(AIOperation)
class AIOperationAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "default_units", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "code")


@admin.register(AIUsageAccount)
class AIUsageAccountAdmin(admin.ModelAdmin):
    list_display = ("photographer", "purchased_balance", "updated_at")
    search_fields = ("photographer__display_name", "photographer__business_name", "photographer__user__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AIUsagePeriod)
class AIUsagePeriodAdmin(admin.ModelAdmin):
    list_display = (
        "account",
        "plan_code_snapshot",
        "starts_at",
        "ends_at",
        "included_allowance",
        "included_consumed",
        "included_reserved",
        "purchased_reserved",
    )
    list_filter = ("plan_code_snapshot", "allowance_limit_type", "starts_at")
    search_fields = ("account__photographer__display_name", "account__photographer__user__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AIUsageTransaction)
class AIUsageTransactionAdmin(admin.ModelAdmin):
    list_display = ("account", "kind", "operation", "included_units", "purchased_units", "created_at")
    list_filter = ("kind", "operation", "created_at")
    search_fields = (
        "account__photographer__display_name",
        "account__photographer__user__email",
        "idempotency_key",
        "source_reference",
    )
    readonly_fields = (
        "account",
        "period",
        "operation",
        "kind",
        "included_units",
        "purchased_units",
        "related_transaction",
        "idempotency_key",
        "source_reference",
        "metadata",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
