from django.db import migrations


GIB = 1024 ** 3

PLAN_DEFINITIONS = {
    "free": {
        "name": "Free",
        "description": "For photographers discovering LumisPixel or starting their business.",
        "sort_order": 10,
        "customer_selectable": True,
        "prices": [("monthly", 0)],
        "allowances": {
            "storage_bytes": ("Storage", "numeric", 5 * GIB, "bytes"),
            "active_galleries": ("Active galleries", "numeric", 3, "galleries"),
            "crm_contacts": ("CRM contacts", "numeric", 25, "contacts"),
            "team_members": ("Team members", "numeric", 1, "members"),
            "ai_monthly_actions": ("Monthly AI image actions", "numeric", 100, "actions"),
        },
        "entitlements": [
            ("basic_photographer_profile", "Basic photographer profile / portfolio"),
            ("lumispixel_subdomain", "LumisPixel subdomain"),
            ("password_protected_galleries", "Password-protected galleries"),
            ("client_favorites", "Client favorites"),
            ("standard_downloads", "Standard downloads"),
            ("basic_watermarking", "Basic watermarking"),
            ("basic_booking", "Basic booking functionality"),
            ("limited_invoices_contracts", "Limited invoices and contracts"),
            ("marketplace_access", "Marketplace/profile access"),
            ("limited_ai", "Limited AI experience"),
        ],
    },
    "pro": {
        "name": "Pro",
        "description": "Complete business tools and meaningful AI capacity for solo professional photographers.",
        "sort_order": 20,
        "customer_selectable": False,
        "prices": [("monthly", 2900), ("annual", 27600)],
        "allowances": {
            "storage_bytes": ("Storage", "numeric", 250 * GIB, "bytes"),
            "active_galleries": ("Active galleries", "unlimited", None, "galleries"),
            "crm_contacts": ("CRM contacts", "unlimited", None, "contacts"),
            "team_members": ("Team members", "numeric", 1, "members"),
            "ai_monthly_actions": ("Monthly AI image actions", "numeric", 2000, "actions"),
        },
        "entitlements": [
            ("full_photographer_website", "Full photographer website"),
            ("custom_domain", "Custom domain"),
            ("remove_lumispixel_branding", "Remove LumisPixel branding"),
            ("unlimited_client_galleries", "Unlimited client galleries"),
            ("unlimited_crm_contacts", "Unlimited CRM contacts"),
            ("booking_calendar", "Booking and calendar tools"),
            ("contracts", "Contracts"),
            ("e_signatures", "E-signatures"),
            ("quotes_questionnaires", "Quotes and questionnaires"),
            ("invoices", "Invoices"),
            ("payments", "Payments"),
            ("client_portal", "Client portal"),
            ("gallery_proofing", "Gallery proofing"),
            ("client_favorites", "Client favorites"),
            ("high_resolution_downloads", "High-resolution downloads"),
            ("digital_sales", "Digital sales"),
            ("custom_watermarks", "Custom watermarks"),
            ("basic_workflow_automation", "Basic workflow automation"),
            ("email_templates", "Email templates"),
            ("business_dashboard", "Business dashboard"),
            ("lead_booking_analytics", "Lead and booking analytics"),
            ("marketplace_enhancements", "Marketplace enhancements"),
            ("ai_photo_search", "AI photo search"),
            ("face_matching", "Face matching"),
            ("duplicate_detection", "Duplicate detection"),
            ("blur_detection", "Blur detection"),
            ("quality_scoring", "Quality scoring"),
            ("ai_culling", "AI culling"),
            ("ai_editing", "AI editing"),
            ("auto_tagging", "Auto-tagging"),
        ],
    },
    "studio": {
        "name": "Studio",
        "description": "Higher capacity, advanced automation, analytics, and collaboration for growing studios.",
        "sort_order": 30,
        "customer_selectable": False,
        "prices": [("monthly", 5900), ("annual", 56400)],
        "allowances": {
            "storage_bytes": ("Storage", "numeric", 1024 * GIB, "bytes"),
            "active_galleries": ("Active galleries", "unlimited", None, "galleries"),
            "crm_contacts": ("CRM contacts", "unlimited", None, "contacts"),
            "team_members": ("Team members", "numeric", 3, "members"),
            "ai_monthly_actions": ("Monthly AI image actions", "numeric", 7500, "actions"),
        },
        "entitlements": [
            ("full_photographer_website", "Full photographer website"),
            ("custom_domain", "Custom domain"),
            ("remove_lumispixel_branding", "Remove LumisPixel branding"),
            ("unlimited_client_galleries", "Unlimited client galleries"),
            ("unlimited_crm_contacts", "Unlimited CRM contacts"),
            ("booking_calendar", "Booking and calendar tools"),
            ("contracts", "Contracts"),
            ("e_signatures", "E-signatures"),
            ("quotes_questionnaires", "Quotes and questionnaires"),
            ("invoices", "Invoices"),
            ("payments", "Payments"),
            ("client_portal", "Client portal"),
            ("gallery_proofing", "Gallery proofing"),
            ("high_resolution_downloads", "High-resolution downloads"),
            ("digital_sales", "Digital sales"),
            ("custom_watermarks", "Custom watermarks"),
            ("ai_photo_search", "AI photo search"),
            ("face_matching", "Face matching"),
            ("duplicate_detection", "Duplicate detection"),
            ("blur_detection", "Blur detection"),
            ("quality_scoring", "Quality scoring"),
            ("ai_culling", "AI culling"),
            ("ai_editing", "AI editing"),
            ("auto_tagging", "Auto-tagging"),
            ("advanced_workflow_automation", "Advanced workflow automation"),
            ("conditional_workflows", "Conditional workflow actions"),
            ("automated_lead_followups", "Automated lead follow-ups"),
            ("automated_booking_sequences", "Automated booking sequences"),
            ("gallery_reminders", "Gallery reminders"),
            ("payment_reminders", "Payment reminders"),
            ("advanced_client_segmentation", "Advanced client segmentation"),
            ("advanced_analytics", "Advanced analytics"),
            ("revenue_reporting", "Revenue reporting"),
            ("conversion_reporting", "Conversion reporting"),
            ("gallery_engagement_analytics", "Gallery engagement analytics"),
            ("marketing_tools", "Marketing tools"),
            ("team_roles_permissions", "Team roles and permissions"),
            ("shared_studio_calendar", "Shared studio calendar"),
            ("team_task_management", "Team task management"),
            ("internal_notes", "Internal notes"),
            ("priority_support", "Priority support"),
        ],
    },
    "enterprise": {
        "name": "Enterprise",
        "description": "Custom capacity, permissions, integrations, support, and commercial terms for complex operations.",
        "sort_order": 40,
        "customer_selectable": False,
        "prices": [("custom", None)],
        "allowances": {
            "storage_bytes": ("Storage", "custom", None, "bytes"),
            "active_galleries": ("Active galleries", "custom", None, "galleries"),
            "crm_contacts": ("CRM contacts", "custom", None, "contacts"),
            "team_members": ("Team members", "custom", None, "members"),
            "ai_monthly_actions": ("Monthly AI image actions", "custom", None, "actions"),
        },
        "entitlements": [
            ("multiple_locations", "Multiple locations"),
            ("multiple_brands", "Multiple brands / business units"),
            ("advanced_permissions", "Advanced permissions"),
            ("bulk_gallery_creation", "Bulk gallery creation"),
            ("bulk_imports", "Bulk imports"),
            ("api_access", "API access"),
            ("webhooks_integrations", "Webhooks and integrations"),
            ("custom_retention_policies", "Custom retention policies"),
            ("migration_assistance", "Migration assistance"),
            ("dedicated_onboarding", "Dedicated onboarding"),
            ("dedicated_account_management", "Dedicated account management"),
            ("sla", "Service-level agreement"),
            ("custom_support", "Custom support"),
            ("volume_pricing", "Volume pricing"),
        ],
    },
}


def seed_plans(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    PlanPrice = apps.get_model("billing", "PlanPrice")
    PlanAllowance = apps.get_model("billing", "PlanAllowance")
    PlanEntitlement = apps.get_model("billing", "PlanEntitlement")
    Subscription = apps.get_model("billing", "Subscription")
    PhotographerProfile = apps.get_model("accounts", "PhotographerProfile")

    plans = {}
    for code, definition in PLAN_DEFINITIONS.items():
        plan, _ = Plan.objects.update_or_create(
            code=code,
            defaults={
                "name": definition["name"],
                "description": definition["description"],
                "sort_order": definition["sort_order"],
                "is_active": True,
                "is_public": True,
                "customer_selectable": definition["customer_selectable"],
            },
        )
        plans[code] = plan

        for interval, amount_cents in definition["prices"]:
            PlanPrice.objects.update_or_create(
                plan=plan,
                billing_interval=interval,
                currency="USD",
                defaults={
                    "amount_cents": amount_cents,
                    "is_active": True,
                    "checkout_enabled": False,
                    "provider_product_id": "",
                    "provider_price_id": "",
                },
            )

        for key, (label, limit_type, value, unit) in definition["allowances"].items():
            PlanAllowance.objects.update_or_create(
                plan=plan,
                key=key,
                defaults={"label": label, "limit_type": limit_type, "value": value, "unit": unit},
            )

        for entitlement_code, label in definition["entitlements"]:
            PlanEntitlement.objects.update_or_create(
                plan=plan,
                code=entitlement_code,
                defaults={"label": label, "enabled": True, "metadata": {}},
            )

    free_plan = plans["free"]
    for photographer_id in PhotographerProfile.objects.values_list("id", flat=True).iterator():
        Subscription.objects.get_or_create(
            photographer_id=photographer_id,
            defaults={
                "plan": free_plan,
                "status": "active",
                "billing_interval": "free",
                "provider": "none",
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_plans, migrations.RunPython.noop),
    ]
