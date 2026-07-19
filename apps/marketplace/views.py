from django.shortcuts import render

from apps.core.views import add, public_page as core_public_page

add("find_photographer", "Find a Photographer", "Products", description="Connect clients with photographers through a future LumisPixel discovery marketplace.")
add("marketplace", "Marketplace", "Business Tools", description="Promote photographer discovery, booking interest, and marketplace growth opportunities.")


def public_page(request, page_key):
    if page_key != "find_photographer":
        return core_public_page(request, page_key)

    context = {
        "frustrations": [
            ("bi-compass", "Not knowing where to start"),
            ("bi-window-stack", "Too many websites"),
            ("bi-images", "Limited portfolios"),
            ("bi-geo-alt", "No local recommendations"),
            ("bi-tags", "Different pricing"),
            ("bi-stars", "Unclear specialties"),
        ],
        "filters": ["Location", "Photography Style", "Wedding", "Portrait", "Sports", "Commercial", "Corporate", "Real Estate", "School", "Budget Range", "Availability", "Ratings", "Languages", "Travel Distance"],
        "photographers": [
            {"name": "Maya Rivera", "role": "Wedding & portrait photographer", "location": "Austin, TX", "experience": "8 years", "specialties": ["Weddings", "Engagement", "Portrait"], "image": "img/landing/gallery/31.jpg", "portfolio": ["img/landing/gallery/38.jpg", "img/landing/gallery/25.jpg"], "availability": "Availability placeholder", "rating": "Ratings placeholder"},
            {"name": "Jordan Lee", "role": "Sports & event photographer", "location": "Denver, CO", "experience": "6 years", "specialties": ["Sports", "Events", "School"], "image": "img/landing/gallery/40.jpg", "portfolio": ["img/landing/gallery/12.jpg", "img/landing/gallery/20.jpg"], "availability": "Availability placeholder", "rating": "Ratings placeholder"},
            {"name": "Elena Brooks", "role": "Commercial & real estate photographer", "location": "Charlotte, NC", "experience": "10 years", "specialties": ["Commercial", "Real Estate", "Corporate"], "image": "img/landing/gallery/39.jpg", "portfolio": ["img/landing/gallery/9.jpg", "img/landing/gallery/41.jpg"], "availability": "Availability placeholder", "rating": "Ratings placeholder"},
        ],
        "comparison_rows": [("Style", "Editorial, natural, cinematic"), ("Experience", "Years, specialties, portfolio depth"), ("Services", "Sessions, events, commercial projects"), ("Coverage Area", "Local service area and travel range"), ("Portfolio", "Featured galleries and recent work"), ("Packages", "Package information when provided"), ("Languages", "Languages listed by photographer"), ("Availability", "Planned calendar visibility")],
        "story_steps": ["Meet Photographer", "View Portfolio", "Read About Their Style", "Browse Previous Work", "Contact", "Book", "Receive Beautiful Memories"],
        "occasions": ["Wedding", "Engagement", "Portrait", "Family", "Graduation", "Sports", "Corporate", "Commercial", "School", "Real Estate", "Drone", "Travel", "Events", "Festivals"],
        "ecosystem": ["Website", "Portfolio", "Client Galleries", "AI Photo Search", "Future Booking", "Business Dashboard", "Marketplace"],
        "roadmap": ["Direct Booking", "Online Scheduling", "Availability Calendar", "Secure Messaging", "Package Builder", "Deposits", "Contracts", "Payments", "Reviews", "Favorites", "Saved Searches"],
        "faqs": [
            ("How do I find photographers near me?", "Use the planned discovery experience to browse by location, specialty, and travel distance."),
            ("Can I search by photography style?", "Yes. LumisPixel is designed to support style and specialty filters as marketplace discovery expands."),
            ("Can I contact photographers directly?", "Direct contact is planned. Current calls to action guide visitors toward account creation and photographer onboarding."),
            ("Can I compare photographers?", "Comparison tools are planned to help clients review style, services, packages, and availability before reaching out."),
            ("Will booking be available?", "Booking, scheduling, deposits, contracts, and payments are roadmap features for future release."),
            ("Can photographers travel?", "Photographers will be able to show travel preferences and coverage areas when marketplace profiles support it."),
            ("How are photographers featured?", "Featured placement is planned to use complete profiles, portfolios, specialties, and marketplace settings."),
            ("Can I save photographers?", "Favorites and saved searches are planned features for a future client discovery release."),
        ],
    }
    return render(request, "marketplace/find_photographer.html", context)
