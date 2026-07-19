from django.shortcuts import render

PAGE_DEFAULTS = {
    "purpose": "Give photographers and clients a clear public overview of how this LumisPixel area will support modern photo discovery, delivery, and business workflows.",
    "benefits": "Centralized galleries, polished client experiences, AI-assisted workflows, and conversion-focused calls to action help teams launch faster without adding backend complexity here.",
    "future": "This landing page prepares the information architecture for deeper product workflows, integrations, and authenticated modules as they are released.",
}

PUBLIC_PAGES = {}

def add(key, title, category, heading=None, description=None, status=""):
    PUBLIC_PAGES[key] = {**PAGE_DEFAULTS, "title": title, "category": category, "heading": heading or title, "description": description or f"Learn how LumisPixel supports {title.lower()} with an AI-ready photography platform.", "status": status}

for key, title in [
    ("products", "Products"), ("solutions", "Solutions"), ("business_tools", "Business Tools"),
    ("sales_store", "Sales & Store"), ("analytics", "Analytics"), ("events", "Events"),
]: add(key, title, "Platform")
for key, title in [
    ("wedding_photography", "Wedding Photography"), ("portrait_photography", "Portrait Photography"), ("sports_photography", "Sports Photography"), ("school_photography", "School Photography"), ("corporate_photography", "Corporate Photography"), ("event_photography", "Event Photography"), ("real_estate_photography", "Real Estate Photography"), ("commercial_photography", "Commercial Photography"), ("studio_photography", "Studio Photography"), ("destination_photography", "Destination Photography"),
]: add(key, title, "Solutions", description=f"A polished landing page for {title.lower()} teams using LumisPixel to organize client delivery, discovery, and growth.")
for key, title, status in [
    ("resources", "Resources", ""), ("how_it_works", "How It Works", ""), ("documentation", "Documentation", "Preview"), ("help_center", "Help Center", ""), ("faq", "FAQ", ""), ("blog", "Blog", ""), ("release_notes", "Release Notes", ""), ("system_status", "System Status", ""), ("tutorials", "Tutorials", ""), ("community", "Community", ""),
]: add(key, title, "Resources", status=status)
for key, title in [
    ("company", "Company"), ("about", "About"), ("our_story", "Our Story"), ("careers", "Careers"), ("partners", "Partners"), ("contact", "Contact"), ("privacy_policy", "Privacy Policy"), ("terms_of_service", "Terms of Service"), ("cookie_policy", "Cookie Policy"), ("accessibility", "Accessibility"),
]: add(key, title, "Company")


def index(request):
    return render(request, "index.html")


def public_page(request, page_key):
    return render(request, "public_landing.html", {"page": PUBLIC_PAGES[page_key]})


def robots_txt(request):
    from django.http import HttpResponse

    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /accounts/",
        "Disallow: /dashboard/",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")
