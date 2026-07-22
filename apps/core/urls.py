from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.index, name="index"),
    path("pricing/", views.pricing, name="pricing"),
    path("products/", views.public_page, {"page_key": "products"}, name="products"),
    path("for-photographers/", views.for_photographers, name="for_photographers"),
    path("solutions/", views.public_page, {"page_key": "solutions"}, name="solutions"),
    path(
        "solutions/wedding-photography/",
        views.public_page,
        {"page_key": "wedding_photography"},
        name="solution_wedding_photography",
    ),
    path(
        "solutions/portrait-photography/",
        views.public_page,
        {"page_key": "portrait_photography"},
        name="solution_portrait_photography",
    ),
    path(
        "solutions/sports-photography/",
        views.public_page,
        {"page_key": "sports_photography"},
        name="solution_sports_photography",
    ),
    path(
        "solutions/school-photography/",
        views.public_page,
        {"page_key": "school_photography"},
        name="solution_school_photography",
    ),
    path(
        "solutions/corporate-photography/",
        views.public_page,
        {"page_key": "corporate_photography"},
        name="solution_corporate_photography",
    ),
    path(
        "solutions/event-photography/",
        views.public_page,
        {"page_key": "event_photography"},
        name="solution_event_photography",
    ),
    path(
        "solutions/real-estate-photography/",
        views.public_page,
        {"page_key": "real_estate_photography"},
        name="solution_real_estate_photography",
    ),
    path(
        "solutions/commercial-photography/",
        views.public_page,
        {"page_key": "commercial_photography"},
        name="solution_commercial_photography",
    ),
    path(
        "solutions/studio-photography/",
        views.public_page,
        {"page_key": "studio_photography"},
        name="solution_studio_photography",
    ),
    path(
        "solutions/destination-photography/",
        views.public_page,
        {"page_key": "destination_photography"},
        name="solution_destination_photography",
    ),
    path(
        "business-hub/",
        views.public_page,
        {"page_key": "business_hub"},
        name="business_hub",
    ),
    path(
        "business-hub/dashboard/",
        views.public_page,
        {"page_key": "business_hub_dashboard"},
        name="business_hub_dashboard",
    ),
    path(
        "business-hub/client-crm/",
        views.public_page,
        {"page_key": "business_hub_client_crm"},
        name="business_hub_client_crm",
    ),
    path(
        "business-hub/booking-calendar/",
        views.public_page,
        {"page_key": "business_hub_booking_calendar"},
        name="business_hub_booking_calendar",
    ),
    path(
        "business-hub/contracts/",
        views.public_page,
        {"page_key": "business_hub_contracts"},
        name="business_hub_contracts",
    ),
    path(
        "business-hub/invoices-payments/",
        views.public_page,
        {"page_key": "business_hub_invoices_payments"},
        name="business_hub_invoices_payments",
    ),
    path(
        "business-hub/workflow-automation/",
        views.public_page,
        {"page_key": "business_hub_workflow_automation"},
        name="business_hub_workflow_automation",
    ),
    path(
        "business-hub/ai-business-assistant/",
        views.public_page,
        {"page_key": "business_hub_ai_business_assistant"},
        name="business_hub_ai_business_assistant",
    ),
    path(
        "business-hub/analytics-reports/",
        views.public_page,
        {"page_key": "business_hub_analytics_reports"},
        name="business_hub_analytics_reports",
    ),
    path(
        "business-hub/marketing-growth/",
        views.public_page,
        {"page_key": "business_hub_marketing_growth"},
        name="business_hub_marketing_growth",
    ),
    path(
        "business-hub/team-operations/",
        views.public_page,
        {"page_key": "business_hub_team_operations"},
        name="business_hub_team_operations",
    ),
    path("resources/", views.public_page, {"page_key": "resources"}, name="resources"),
    path(
        "resources/how-it-works/",
        views.public_page,
        {"page_key": "how_it_works"},
        name="how_it_works",
    ),
    path(
        "resources/documentation/",
        views.public_page,
        {"page_key": "documentation"},
        name="documentation",
    ),
    path(
        "resources/help-center/",
        views.public_page,
        {"page_key": "help_center"},
        name="help_center",
    ),
    path("resources/faq/", views.public_page, {"page_key": "faq"}, name="faq"),
    path("resources/blog/", views.public_page, {"page_key": "blog"}, name="blog"),
    path(
        "resources/release-notes/",
        views.public_page,
        {"page_key": "release_notes"},
        name="release_notes",
    ),
    path(
        "resources/system-status/",
        views.public_page,
        {"page_key": "system_status"},
        name="system_status",
    ),
    path(
        "resources/tutorials/",
        views.public_page,
        {"page_key": "tutorials"},
        name="tutorials",
    ),
    path(
        "resources/community/",
        views.public_page,
        {"page_key": "community"},
        name="community",
    ),
    path("company/", views.public_page, {"page_key": "company"}, name="company"),
    path("company/about/", views.public_page, {"page_key": "about"}, name="about"),
    path(
        "company/our-story/",
        views.public_page,
        {"page_key": "our_story"},
        name="our_story",
    ),
    path(
        "company/careers/", views.public_page, {"page_key": "careers"}, name="careers"
    ),
    path(
        "company/partners/",
        views.public_page,
        {"page_key": "partners"},
        name="partners",
    ),
    path(
        "company/contact/", views.public_page, {"page_key": "contact"}, name="contact"
    ),
    path(
        "company/privacy-policy/",
        views.public_page,
        {"page_key": "privacy_policy"},
        name="privacy_policy",
    ),
    path(
        "company/terms-of-service/",
        views.public_page,
        {"page_key": "terms_of_service"},
        name="terms_of_service",
    ),
    path(
        "company/cookie-policy/",
        views.public_page,
        {"page_key": "cookie_policy"},
        name="cookie_policy",
    ),
    path(
        "company/accessibility/",
        views.public_page,
        {"page_key": "accessibility"},
        name="accessibility",
    ),
    path("robots.txt", views.robots_txt, name="robots_txt"),
]
