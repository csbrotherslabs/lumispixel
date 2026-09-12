from django.contrib import admin

from .models import Plan, PlanAllowance, PlanEntitlement, PlanPrice, Subscription


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
