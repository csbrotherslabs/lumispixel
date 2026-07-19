from django.shortcuts import render

PAGE_DEFAULTS = {
    "purpose": "Give photographers and clients a clear public overview of how this LumisPixel area will support modern photo discovery, delivery, and business workflows.",
    "benefits": "Centralized galleries, polished client experiences, AI-assisted workflows, and conversion-focused calls to action help teams launch faster without adding backend complexity here.",
    "future": "This landing page prepares the information architecture for deeper product workflows, integrations, and authenticated modules as they are released.",
}

PUBLIC_PAGES = {}


def add(key, title, category, heading=None, description=None, status=""):
    PUBLIC_PAGES[key] = {
        **PAGE_DEFAULTS,
        "title": title,
        "category": category,
        "heading": heading or title,
        "description": description
        or f"Learn how LumisPixel supports {title.lower()} with an AI-ready photography platform.",
        "status": status,
    }


for key, title in [
    ("products", "Products"),
    ("solutions", "Solutions"),
    ("business_tools", "Business Tools"),
    ("sales_store", "Sales & Store"),
    ("analytics", "Analytics"),
    ("events", "Events"),
]:
    add(key, title, "Platform")
for key, title in [
    ("wedding_photography", "Wedding Photography"),
    ("portrait_photography", "Portrait Photography"),
    ("sports_photography", "Sports Photography"),
    ("school_photography", "School Photography"),
    ("corporate_photography", "Corporate Photography"),
    ("event_photography", "Event Photography"),
    ("real_estate_photography", "Real Estate Photography"),
    ("commercial_photography", "Commercial Photography"),
    ("studio_photography", "Studio Photography"),
    ("destination_photography", "Destination Photography"),
]:
    add(
        key,
        title,
        "Solutions",
        description=f"A polished landing page for {title.lower()} teams using LumisPixel to organize client delivery, discovery, and growth.",
    )
for key, title, status in [
    ("resources", "Resources", ""),
    ("how_it_works", "How It Works", ""),
    ("documentation", "Documentation", "Preview"),
    ("help_center", "Help Center", ""),
    ("faq", "FAQ", ""),
    ("blog", "Blog", ""),
    ("release_notes", "Release Notes", ""),
    ("system_status", "System Status", ""),
    ("tutorials", "Tutorials", ""),
    ("community", "Community", ""),
]:
    add(key, title, "Resources", status=status)
for key, title in [
    ("company", "Company"),
    ("about", "About"),
    ("our_story", "Our Story"),
    ("careers", "Careers"),
    ("partners", "Partners"),
    ("contact", "Contact"),
    ("privacy_policy", "Privacy Policy"),
    ("terms_of_service", "Terms of Service"),
    ("cookie_policy", "Cookie Policy"),
    ("accessibility", "Accessibility"),
]:
    add(key, title, "Company")


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


def for_photographers(request):
    context = {
        "pain_points": [
            {
                "icon": "bi-images",
                "text": "Thousands of photos to organize after every shoot.",
            },
            {
                "icon": "bi-chat-dots",
                "text": "Clients asking, “Do you have my photos?”",
            },
            {
                "icon": "bi-cloud-arrow-up",
                "text": "Hours spent uploading galleries and sending links.",
            },
            {
                "icon": "bi-bag-x",
                "text": "Lost print sales because buying is disconnected.",
            },
            {
                "icon": "bi-grid-3x3-gap",
                "text": "Multiple apps for galleries, websites, CRM, sales, and analytics.",
            },
            {
                "icon": "bi-search",
                "text": "Difficult searching across events, people, and moments.",
            },
            {
                "icon": "bi-window",
                "text": "No professional website that reflects your brand.",
            },
            {
                "icon": "bi-graph-up",
                "text": "Limited business insights when every tool reports separately.",
            },
        ],
        "workflow": [
            "Client books session",
            "Create Event",
            "Shoot",
            "Upload Photos",
            "AI Organizes",
            "Client Finds Photos",
            "Sell Photos",
            "Grow Business",
        ],
        "features": [
            {
                "title": "Photographer Workspace",
                "copy": "A calm command center for the business side of photography—clients, events, billing, analytics, orders, and marketing in one place.",
                "bullets": [
                    "Dashboard, clients, and events",
                    "Billing, orders, and revenue",
                    "Marketing and business visibility",
                ],
                "image": "img/landing/gallery/31.jpg",
                "alt": "Photographer reviewing a business workspace",
                "callout": "Studio overview",
                "micro": "Know what needs attention today.",
            },
            {
                "title": "AI Photo Search",
                "copy": "Help clients find themselves and their moments without scrolling through thousands of images.",
                "bullets": [
                    "Face recognition and selfie search",
                    "Semantic, event, and people search",
                    "Auto tagging for faster discovery",
                ],
                "image": "img/landing/gallery/38.jpg",
                "alt": "Client gallery search experience",
                "callout": "Selfie search",
                "micro": "The right photos in seconds.",
            },
            {
                "title": "AI Editing & Culling",
                "copy": "Reduce review time with intelligent signals that surface quality issues and likely keepers.",
                "bullets": [
                    "Blur and closed-eye detection",
                    "Quality scoring and duplicates",
                    "Best image selection and editing assistance",
                ],
                "image": "img/landing/gallery/25.jpg",
                "alt": "Photographer selecting best images",
                "callout": "Smart culling",
                "micro": "Less sorting. More creating.",
            },
            {
                "title": "Client Galleries",
                "copy": "Deliver premium galleries that are easy for clients to access, share, favorite, download, and buy from.",
                "bullets": [
                    "Password protection and watermarks",
                    "Favorites, downloads, QR codes",
                    "Event codes for fast access",
                ],
                "image": "img/landing/gallery/40.jpg",
                "alt": "Beautiful online client gallery",
                "callout": "Client-ready",
                "micro": "Beautiful delivery every time.",
            },
            {
                "title": "Photographer Websites",
                "copy": "Launch a professional web presence that turns visitors into inquiries and makes your work feel premium.",
                "bullets": [
                    "Portfolio and theme selection",
                    "Branding, SEO, and contact pages",
                    "Professional websites for every specialty",
                ],
                "image": "img/landing/gallery/20.jpg",
                "alt": "Photography website portfolio",
                "callout": "Brand home",
                "micro": "Your portfolio, polished.",
            },
            {
                "title": "Sales & Store",
                "copy": "Turn gallery attention into revenue with products clients can purchase while excitement is high.",
                "bullets": [
                    "Digital downloads, prints, and frames",
                    "Albums, packages, and gift cards",
                    "Coupons for campaigns and events",
                ],
                "image": "img/landing/gallery/12.jpg",
                "alt": "Photography print and album sales",
                "callout": "Built-in sales",
                "micro": "Capture demand in the moment.",
            },
            {
                "title": "Business Analytics",
                "copy": "Understand what is working across revenue, downloads, gallery views, popular images, and client engagement.",
                "bullets": [
                    "Revenue and sales performance",
                    "Downloads and gallery views",
                    "Popular images and client engagement",
                ],
                "image": "img/landing/gallery/9.jpg",
                "alt": "Analytics for photography business",
                "callout": "Live insights",
                "micro": "Make growth visible.",
            },
            {
                "title": "Marketplace",
                "copy": "Prepare your studio for a connected ecosystem of requests, collaborators, second shooters, editors, and future client discovery.",
                "bullets": [
                    "Photography requests",
                    "Second shooters, retouchers, and editors",
                    "Future client marketplace",
                ],
                "image": "img/landing/gallery/15.jpg",
                "alt": "Photography marketplace collaboration",
                "callout": "Growth network",
                "micro": "More ways to expand.",
            },
        ],
        "ai_tools": [
            "Face Recognition",
            "Smart Search",
            "Quality Detection",
            "Blur Detection",
            "Duplicate Detection",
            "Auto Tagging",
            "Editing Assistance",
            "Smart Collections",
            "Semantic Search",
            "Future AI Recommendations",
        ],
        "comparison": [
            {
                "category": "Gallery delivery",
                "traditional": "Upload, copy links, explain access, repeat.",
                "lumis": "Branded galleries with event codes, favorites, downloads, and sales.",
            },
            {
                "category": "Website",
                "traditional": "Separate site builder and disconnected portfolio.",
                "lumis": "Photography websites, themes, branding, SEO, and contact pages.",
            },
            {
                "category": "AI Search",
                "traditional": "Manual folders and endless scrolling.",
                "lumis": "Face, selfie, semantic, and event search.",
            },
            {
                "category": "AI Culling",
                "traditional": "Manual checks for blur, duplicates, and closed eyes.",
                "lumis": "Quality signals, duplicate detection, and best image selection.",
            },
            {
                "category": "Online Sales",
                "traditional": "Separate store or missed print demand.",
                "lumis": "Downloads, prints, albums, frames, packages, coupons, and gift cards.",
            },
            {
                "category": "Business Dashboard",
                "traditional": "Spreadsheets and scattered apps.",
                "lumis": "Clients, events, billing, orders, analytics, and marketing.",
            },
            {
                "category": "Marketplace",
                "traditional": "Text threads and informal referrals.",
                "lumis": "Requests, collaborators, second shooters, retouchers, and editors.",
            },
            {
                "category": "Client Selfie Search",
                "traditional": "Clients ask you to find their photos.",
                "lumis": "Clients upload a selfie and find images instantly.",
            },
        ],
        "photographer_types": [
            {"name": n, "icon": i}
            for n, i in [
                ("Wedding", "bi-heart"),
                ("Portrait", "bi-person-square"),
                ("Sports", "bi-trophy"),
                ("School", "bi-mortarboard"),
                ("Corporate", "bi-briefcase"),
                ("Commercial", "bi-badge-ad"),
                ("Events", "bi-calendar-event"),
                ("Real Estate", "bi-house"),
                ("Studio", "bi-camera"),
                ("Travel", "bi-airplane"),
                ("Families", "bi-people"),
                ("Drone", "bi-broadcast"),
            ]
        ],
        "roadmap": [
            {
                "status": "Future",
                "title": "AI Editing",
                "copy": "Faster style-aware edits and assistive adjustments.",
            },
            {
                "status": "Future",
                "title": "AI Album Design",
                "copy": "Album layouts generated from story, emotion, and selections.",
            },
            {
                "status": "Future",
                "title": "Marketing Assistant",
                "copy": "Campaign ideas, email drafts, and sales nudges.",
            },
            {
                "status": "Future",
                "title": "Mobile App",
                "copy": "On-the-go studio operations and client access.",
            },
            {
                "status": "Expanding",
                "title": "Marketplace",
                "copy": "Requests, collaborators, and discovery.",
            },
            {
                "status": "Future",
                "title": "Studio CRM",
                "copy": "Relationship history and pipeline management.",
            },
            {
                "status": "Future",
                "title": "Booking System",
                "copy": "Availability, deposits, packages, and scheduling.",
            },
            {
                "status": "Future",
                "title": "Smart Contracts",
                "copy": "Templates and guided client agreements.",
            },
        ],
        "testimonials": [
            {
                "text": "This feels like it was designed by someone who understands gallery delivery, client questions, and the chaos after a big event.",
                "role": "Placeholder testimonial — wedding photographer",
            },
            {
                "text": "The promise is simple: fewer disconnected tools, faster client discovery, and more opportunities to sell the work I already created.",
                "role": "Placeholder testimonial — sports photographer",
            },
            {
                "text": "I want my website, galleries, orders, and analytics to finally speak the same language. LumisPixel is aiming directly at that gap.",
                "role": "Placeholder testimonial — portrait studio owner",
            },
        ],
        "faqs": [
            {
                "q": "Can clients upload selfies?",
                "a": "Yes. LumisPixel is designed around selfie-based discovery so clients can find their own images quickly inside supported galleries.",
            },
            {
                "q": "Can I sell prints?",
                "a": "The sales vision includes prints, frames, albums, packages, digital downloads, coupons, and gift cards from gallery experiences.",
            },
            {
                "q": "Can I use my own branding?",
                "a": "Yes. Photographer websites and galleries are planned around themes, branding, portfolio presentation, SEO, and professional contact pages.",
            },
            {
                "q": "Can clients download photos?",
                "a": "Yes. Client galleries include download-focused workflows, with controls such as passwords, favorites, watermarks, QR codes, and event codes.",
            },
            {
                "q": "How does AI work?",
                "a": "AI supports search, face recognition, quality detection, blur detection, duplicate detection, auto tagging, smart collections, and future recommendations.",
            },
            {
                "q": "Can I migrate from another gallery provider?",
                "a": "Migration tooling will require backend implementation, but the page and product direction are built for photographers replacing multiple existing tools.",
            },
            {
                "q": "What file formats are supported?",
                "a": "Final production file-format support should be confirmed by backend upload and processing services as they are implemented.",
            },
            {
                "q": "How secure are my galleries?",
                "a": "The experience is designed for protected galleries with passwords, event codes, watermarks, and controlled downloads; production security depends on backend enforcement.",
            },
        ],
    }
    return render(request, "for_photographers.html", context)
