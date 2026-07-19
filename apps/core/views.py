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
    if page_key == "wedding_photography":
        return wedding_photography(request)
    if page_key == "portrait_photography":
        return portrait_photography(request)
    if page_key == "sports_photography":
        return sports_photography(request)
    if page_key == "school_photography":
        return school_photography(request)
    if page_key == "corporate_photography":
        return corporate_photography(request)
    if page_key == "event_photography":
        return event_photography(request)
    return render(request, "public_landing.html", {"page": PUBLIC_PAGES[page_key]})


def wedding_photography(request):
    context = {
        "stats": [
            "Culling",
            "Face Recognition",
            "Client Galleries",
            "Print Sales",
        ],
        "photographer_cards": [
            ("bi-stars", "Culling"),
            ("bi-magic", "Editing"),
            ("bi-images", "Galleries"),
            ("bi-graph-up-arrow", "Sales"),
        ],
        "features": [
            ("bi-funnel", "AI Culling", "Quickly identify your strongest images."),
            ("bi-magic", "Editing Assistance", "Speed up repetitive editing tasks."),
            (
                "bi-person-bounding-box",
                "Face Recognition",
                "Organize couples, families, and guests automatically.",
            ),
            (
                "bi-images",
                "Client Galleries",
                "Deliver polished galleries on any device.",
            ),
            (
                "bi-search-heart",
                "Photo Search",
                "Help guests find their photos with a selfie.",
            ),
            (
                "bi-window",
                "Photographer Websites",
                "Showcase your work and attract new clients.",
            ),
            ("bi-bag-heart", "Print Sales", "Sell prints, albums, and downloads."),
            (
                "bi-chat-dots",
                "Client Management",
                "Manage inquiries, bookings, and communication.",
            ),
            (
                "bi-bar-chart",
                "Analytics",
                "Track galleries, sales, and client activity.",
            ),
        ],
        "pain_solutions": [
            ("Too Many Photos", "Faster Culling"),
            ("Long Editing Hours", "Editing Assistance"),
            ("Slow Delivery", "Easy Gallery Delivery"),
            ("Missed Sales", "Built-In Sales"),
            ("Too Many Tools", "Selfie Photo Search"),
            ("Repeated Client Requests", "One Connected Platform"),
        ],
        "guest_cards": [
            (
                "bi-search-heart",
                "Find My Photos",
                "Use a selfie to locate matching images.",
            ),
            ("bi-grid", "Online Galleries", "Browse photos from any device."),
            ("bi-heart", "Favorites", "Save images for albums and prints."),
            (
                "bi-shield-check",
                "Secure Downloads",
                "Access approved high-resolution files.",
            ),
            (
                "bi-bag-check",
                "Print Ordering",
                "Order prints directly from the gallery.",
            ),
            ("bi-share", "Easy Sharing", "Share photos with friends and family."),
        ],
        "timeline": [
            "Book",
            "Capture",
            "Upload",
            "Cull",
            "Edit",
            "Organize",
            "Deliver",
            "Search",
            "Download",
            "Order",
            "Share",
        ],
        "testimonials": [
            (
                "LumisPixel helps us organize wedding galleries faster and keep delivery simple for clients.",
                "Wedding photographer",
            ),
            (
                "Guests can find their photos without asking us to search through folders after delivery.",
                "Studio owner",
            ),
            (
                "Our gallery was easy to use, and ordering prints felt simple.",
                "Wedding client",
            ),
        ],
        "metrics": [
            "Faster Organization",
            "Easier Photo Search",
            "More Sales Opportunities",
            "One Connected Workflow",
        ],
        "faqs": [
            (
                "How does selfie photo search work?",
                "Guests upload a selfie when the photographer enables search. LumisPixel finds matching photos in the gallery.",
            ),
            (
                "How many photos can I upload?",
                "LumisPixel supports large wedding galleries. Upload limits depend on your plan and storage tier.",
            ),
            (
                "Can I sell prints and albums?",
                "Yes. You can offer prints, albums, downloads, and other products from the gallery.",
            ),
            (
                "Can I create multiple galleries?",
                "Yes. Create separate galleries for weddings, couples, clients, or events.",
            ),
            (
                "Can clients download full-resolution photos?",
                "Yes. Photographers control download access for each gallery and package.",
            ),
            (
                "Which tools can LumisPixel replace?",
                "It can replace separate tools for galleries, websites, search, sales, client messages, and analytics.",
            ),
        ],
    }
    return render(request, "wedding_photography.html", context)


def portrait_photography(request):
    context = {
        "stats": [
            "AI Photo Search",
            "Online Galleries",
            "Print Sales",
            "Client Management",
        ],
        "photographer_cards": [
            ("bi-stars", "AI Culling"),
            ("bi-magic", "Editing Assistance"),
            ("bi-images", "Client Galleries"),
            ("bi-graph-up-arrow", "Business Growth"),
        ],
        "features": [
            ("bi-funnel", "AI Culling", "Quickly sort your best images."),
            ("bi-magic", "Editing Assistance", "Reduce repetitive editing work."),
            (
                "bi-person-bounding-box",
                "Face Recognition",
                "Organize every client automatically.",
            ),
            ("bi-images", "Client Galleries", "Deliver polished online galleries."),
            (
                "bi-search-heart",
                "Photo Search",
                "Clients find their photos with a selfie.",
            ),
            ("bi-window", "Photographer Websites", "Showcase your portfolio."),
            ("bi-bag-heart", "Print Sales", "Sell prints and digital downloads."),
            ("bi-chat-dots", "Client Management", "Manage bookings and communication."),
            ("bi-bar-chart", "Analytics", "Track sales and gallery activity."),
        ],
        "pain_solutions": [
            ("Finding New Clients", "Better Workflow"),
            ("Editing Time", "Faster Editing"),
            ("Gallery Delivery", "Easy Galleries"),
            ("Missed Print Sales", "Built-In Store"),
            ("Multiple Software Tools", "One Platform"),
            ("Client Communication", "Happy Clients"),
        ],
        "guest_cards": [
            ("bi-search-heart", "Find My Photos", "Use a selfie to find portraits."),
            ("bi-grid", "Online Galleries", "Browse portraits from any device."),
            ("bi-heart", "Favorites", "Save favorite images for later."),
            ("bi-shield-check", "Secure Downloads", "Download approved files safely."),
            ("bi-bag-check", "Print Ordering", "Order prints from the gallery."),
            ("bi-share", "Easy Sharing", "Share portraits with family."),
        ],
        "timeline": [
            "Book Session",
            "Capture",
            "Upload",
            "Cull",
            "Edit",
            "Organize",
            "Gallery",
            "Search",
            "Download",
            "Print Order",
            "Share",
        ],
        "testimonials": [
            (
                "LumisPixel keeps sessions organized and makes gallery delivery feel simple.",
                "Portrait photographer",
            ),
            (
                "Clients find favorites quickly, which helps us sell prints without extra emails.",
                "Studio owner",
            ),
            (
                "Our portrait gallery was easy to browse, download, and share with family.",
                "Portrait client",
            ),
        ],
        "metrics": [
            "Better Organization",
            "Faster Delivery",
            "More Print Sales",
            "One Connected Workflow",
        ],
        "faqs": [
            (
                "How does selfie photo search work?",
                "Clients upload a selfie when search is enabled. LumisPixel finds matching portraits in the gallery.",
            ),
            (
                "Can clients download full-resolution photos?",
                "Yes. Photographers control download access by gallery and package.",
            ),
            (
                "Can I sell prints?",
                "Yes. You can sell prints and digital downloads from each gallery.",
            ),
            (
                "Can I create multiple galleries?",
                "Yes. Create galleries for sessions, clients, families, or campaigns.",
            ),
            (
                "Can I organize clients automatically?",
                "Yes. Face recognition helps organize people across portrait galleries.",
            ),
            (
                "Which tools can LumisPixel replace?",
                "It can replace separate tools for editing, galleries, websites, stores, messages, and analytics.",
            ),
        ],
    }
    return render(request, "portrait_photography.html", context)


def sports_photography(request):
    context = {
        "stats": [
            "AI Photo Search",
            "Online Galleries",
            "Team Galleries",
            "Print Sales",
        ],
        "photographer_cards": [
            ("bi-stars", "AI Culling"),
            ("bi-person-bounding-box", "Face Recognition"),
            ("bi-collection", "Team Galleries"),
            ("bi-graph-up-arrow", "Business Growth"),
        ],
        "features": [
            ("bi-funnel", "AI Culling", "Quickly remove duplicates and missed shots."),
            ("bi-magic", "Editing Assistance", "Reduce repetitive editing work."),
            (
                "bi-person-bounding-box",
                "Face Recognition",
                "Organize athletes automatically.",
            ),
            ("bi-collection", "Team Galleries", "Create galleries by team or event."),
            ("bi-search-heart", "Photo Search", "Find photos with a selfie."),
            ("bi-window", "Photographer Websites", "Showcase your sports portfolio."),
            ("bi-bag-heart", "Print Sales", "Sell prints, banners, and downloads."),
            (
                "bi-chat-dots",
                "Client Management",
                "Manage teams, leagues, and communication.",
            ),
            ("bi-bar-chart", "Analytics", "Track gallery views and sales."),
        ],
        "pain_solutions": [
            ("Thousands of Photos", "Faster Culling"),
            ("Fast Turnaround", "AI Face Search"),
            ("Finding Athletes", "Organized Galleries"),
            ("Multiple Teams", "Easy Delivery"),
            ("Missed Sales", "Built-In Store"),
            ("Too Many Tools", "One Platform"),
        ],
        "guest_cards": [
            (
                "bi-search-heart",
                "Find My Photos",
                "Use a selfie to locate game photos.",
            ),
            ("bi-collection", "Team Galleries", "Browse photos by team or event."),
            ("bi-heart", "Favorites", "Save favorite action shots."),
            ("bi-shield-check", "Secure Downloads", "Download approved files safely."),
            ("bi-bag-check", "Print Ordering", "Order prints and banners online."),
            ("bi-share", "Easy Sharing", "Share highlights with family and teammates."),
        ],
        "timeline": [
            "Book Event",
            "Capture",
            "Upload",
            "Cull",
            "Edit",
            "Organize",
            "Publish Gallery",
            "Search",
            "Download",
            "Print Order",
            "Share",
        ],
        "testimonials": [
            (
                "LumisPixel helps us sort game-day photos faster and publish galleries while families are still excited.",
                "Sports photographer",
            ),
            (
                "Selfie search makes athlete discovery simple. Parents spend less time scrolling and more time ordering favorites.",
                "Tournament photographer",
            ),
            (
                "Team galleries keep everything organized, and built-in print sales make banners and downloads easy.",
                "Studio owner",
            ),
        ],
        "metrics": [
            "Faster Organization",
            "Easy Athlete Search",
            "More Print Sales",
            "One Connected Workflow",
        ],
        "faqs": [
            (
                "How does selfie photo search work?",
                "Athletes or parents upload a selfie when search is enabled. LumisPixel finds matching photos in the gallery.",
            ),
            (
                "Can I create galleries for multiple teams?",
                "Yes. Create galleries by team, league, tournament, or event.",
            ),
            (
                "Can parents download full-resolution photos?",
                "Yes. Photographers control download access for each gallery and package.",
            ),
            (
                "Can I sell prints and banners?",
                "Yes. Sell prints, banners, downloads, and other products from the gallery.",
            ),
            (
                "Can I organize athletes automatically?",
                "Yes. Face recognition helps group athletes across high-volume galleries.",
            ),
            (
                "Which tools can LumisPixel replace?",
                "It can replace separate tools for editing, galleries, websites, stores, messages, search, and analytics.",
            ),
        ],
    }
    return render(request, "sports_photography.html", context)


def school_photography(request):
    context = {
        "stats": [
            "AI Photo Search",
            "Student Galleries",
            "Online Ordering",
            "Print Sales",
        ],
        "photographer_cards": [
            ("bi-stars", "AI Culling"),
            ("bi-person-bounding-box", "Face Recognition"),
            ("bi-images", "Student Galleries"),
            ("bi-graph-up-arrow", "Business Growth"),
        ],
        "features": [
            ("bi-funnel", "AI Culling", "Quickly sort your best photos."),
            ("bi-magic", "Editing Assistance", "Reduce repetitive editing work."),
            (
                "bi-person-bounding-box",
                "Face Recognition",
                "Organize students automatically.",
            ),
            (
                "bi-images",
                "Student Galleries",
                "Create secure galleries for every student.",
            ),
            (
                "bi-search-heart",
                "Photo Search",
                "Parents find student photos with a selfie.",
            ),
            (
                "bi-window",
                "Photographer Websites",
                "Promote your school photography services.",
            ),
            (
                "bi-bag-heart",
                "Print Sales",
                "Sell print packages and digital downloads.",
            ),
            (
                "bi-chat-dots",
                "Client Management",
                "Manage schools, classes, and communication.",
            ),
            ("bi-bar-chart", "Analytics", "Track orders, galleries, and sales."),
        ],
        "pain_solutions": [
            ("Thousands of Students", "Faster Organization"),
            ("Picture Day Deadlines", "AI Face Search"),
            ("Finding Students", "Secure Galleries"),
            ("Multiple Schools", "Easy Delivery"),
            ("Print Orders", "Built-In Store"),
            ("Too Many Tools", "One Platform"),
        ],
        "guest_cards": [
            (
                "bi-search-heart",
                "Find My Photos",
                "Use a selfie to locate school photos.",
            ),
            ("bi-images", "Student Galleries", "View photos in a private gallery."),
            ("bi-heart", "Favorites", "Save favorite poses for ordering."),
            ("bi-shield-check", "Secure Downloads", "Download approved files safely."),
            ("bi-bag-check", "Online Ordering", "Order prints and downloads online."),
            ("bi-share", "Easy Sharing", "Share photos with family."),
        ],
        "timeline": [
            "Book School",
            "Picture Day",
            "Upload",
            "Cull",
            "Edit",
            "Organize",
            "Publish Galleries",
            "Photo Search",
            "Order Prints",
            "Download",
            "Share",
        ],
        "testimonials": [
            (
                "LumisPixel helps us organize students faster and deliver galleries before picture day questions pile up.",
                "School photographer",
            ),
            (
                "Parents find their child quickly, choose favorites, and order prints without extra emails.",
                "Studio owner",
            ),
            (
                "Picture day feels smoother when galleries, search, and orders stay in one place.",
                "School coordinator",
            ),
        ],
        "metrics": [
            "Faster Student Organization",
            "Easier Parent Search",
            "More Print Orders",
            "One Connected Workflow",
        ],
        "faqs": [
            (
                "How does selfie photo search work?",
                "Parents upload a selfie when search is enabled. LumisPixel finds matching student photos in the gallery.",
            ),
            (
                "Can parents order photos online?",
                "Yes. Parents can order print packages and digital downloads from the gallery.",
            ),
            (
                "Can I create galleries for each student?",
                "Yes. You can create secure galleries organized around each student.",
            ),
            (
                "Can schools have private galleries?",
                "Yes. Photographers can keep school galleries private and control access.",
            ),
            (
                "Can I sell print packages?",
                "Yes. LumisPixel supports print packages, downloads, and online ordering.",
            ),
            (
                "Which tools can LumisPixel replace?",
                "It can replace separate tools for editing, galleries, websites, stores, parent communication, search, and analytics.",
            ),
        ],
    }
    return render(request, "school_photography.html", context)


def corporate_photography(request):
    context = {
        "stats": [
            "AI Photo Search",
            "Private Galleries",
            "Team Galleries",
            "Digital Downloads",
        ],
        "photographer_cards": [
            ("bi-stars", "AI Culling"),
            ("bi-person-bounding-box", "Face Recognition"),
            ("bi-images", "Private Galleries"),
            ("bi-graph-up-arrow", "Business Growth"),
        ],
        "features": [
            ("bi-funnel", "AI Culling", "Quickly sort your best images."),
            ("bi-magic", "Editing Assistance", "Reduce repetitive editing work."),
            (
                "bi-person-bounding-box",
                "Face Recognition",
                "Organize employees and attendees automatically.",
            ),
            (
                "bi-images",
                "Private Galleries",
                "Deliver secure galleries for every client.",
            ),
            (
                "bi-search-heart",
                "Photo Search",
                "Employees find their photos with a selfie.",
            ),
            ("bi-window", "Photographer Websites", "Showcase your business portfolio."),
            (
                "bi-cloud-download",
                "Digital Downloads",
                "Deliver high-resolution files with ease.",
            ),
            (
                "bi-chat-dots",
                "Client Management",
                "Manage companies, events, and communication.",
            ),
            (
                "bi-bar-chart",
                "Analytics",
                "Track galleries, downloads, and engagement.",
            ),
        ],
        "pain_solutions": [
            ("Large Events", "Faster Organization"),
            ("Tight Deadlines", "AI Face Search"),
            ("Finding Attendees", "Private Galleries"),
            ("Multiple Clients", "Easy Delivery"),
            ("Secure Delivery", "Secure Sharing"),
            ("Too Many Tools", "One Platform"),
        ],
        "guest_cards": [
            (
                "bi-search-heart",
                "Find My Photos",
                "Use a selfie to locate event photos.",
            ),
            ("bi-images", "Private Galleries", "Access approved client galleries."),
            ("bi-heart", "Favorites", "Save images for review."),
            ("bi-shield-check", "Secure Downloads", "Download approved files safely."),
            ("bi-share", "Easy Sharing", "Share photos with approved teams."),
            ("bi-people", "Team Access", "Give organizers controlled gallery access."),
        ],
        "timeline": [
            "Book Client",
            "Capture",
            "Upload",
            "Cull",
            "Edit",
            "Organize",
            "Publish Gallery",
            "Photo Search",
            "Download",
            "Share",
        ],
        "testimonials": [
            (
                "Corporate galleries stay organized, and delivery feels faster for every event client.",
                "Corporate photographer",
            ),
            (
                "Employees find headshots and conference images without extra requests to our team.",
                "Event organizer",
            ),
            (
                "LumisPixel keeps our workflow simple from upload to secure client delivery.",
                "Studio owner",
            ),
        ],
        "metrics": [
            "Faster Organization",
            "Easy Employee Search",
            "Secure Delivery",
            "One Connected Workflow",
        ],
        "faqs": [
            (
                "How does selfie photo search work?",
                "Employees upload a selfie when search is enabled. LumisPixel finds matching photos in the gallery.",
            ),
            (
                "Can I create private client galleries?",
                "Yes. Create private galleries for companies, events, teams, or headshot sessions.",
            ),
            (
                "Can employees download high-resolution photos?",
                "Yes. Photographers control which files employees can download.",
            ),
            (
                "Can I organize multiple events?",
                "Yes. Manage separate companies, events, galleries, and communication in one place.",
            ),
            (
                "Is gallery access secure?",
                "Yes. Private galleries and controlled downloads help protect client access.",
            ),
            (
                "Which tools can LumisPixel replace?",
                "It can replace tools for editing, galleries, face search, websites, file sharing, messages, and analytics.",
            ),
        ],
    }
    return render(request, "corporate_photography.html", context)


def event_photography(request):
    context = {
        "stats": [
            "AI Photo Search",
            "Private Galleries",
            "Event Galleries",
            "Digital Downloads",
        ],
        "photographer_cards": [
            ("bi-stars", "AI Culling"),
            ("bi-person-bounding-box", "Face Recognition"),
            ("bi-images", "Event Galleries"),
            ("bi-graph-up-arrow", "Business Growth"),
        ],
        "features": [
            ("bi-funnel", "AI Culling", "Quickly sort your best images."),
            ("bi-magic", "Editing Assistance", "Reduce repetitive editing work."),
            ("bi-person-bounding-box", "Face Recognition", "Organize attendees automatically."),
            ("bi-images", "Event Galleries", "Create galleries for every event."),
            ("bi-search-heart", "Photo Search", "Guests find their photos with a selfie."),
            ("bi-window", "Photographer Websites", "Showcase your event portfolio."),
            ("bi-cloud-download", "Print & Downloads", "Sell prints and digital files."),
            ("bi-chat-dots", "Client Management", "Manage events and communication."),
            ("bi-bar-chart", "Analytics", "Track galleries, downloads, and sales."),
        ],
        "pain_solutions": [
            ("Large Crowds", "Faster Organization"),
            ("Tight Deadlines", "AI Face Search"),
            ("Finding Guests", "Event Galleries"),
            ("Multiple Events", "Easy Delivery"),
            ("Missed Sales", "Built-In Store"),
            ("Too Many Tools", "One Platform"),
        ],
        "guest_cards": [
            ("bi-search-heart", "Find My Photos", "Use a selfie to locate event photos."),
            ("bi-images", "Event Galleries", "Browse photos from every event."),
            ("bi-heart", "Favorites", "Save favorite moments for later."),
            ("bi-shield-check", "Secure Downloads", "Download approved files safely."),
            ("bi-bag-check", "Print Ordering", "Order prints from the gallery."),
            ("bi-share", "Easy Sharing", "Share photos with friends and teams."),
        ],
        "timeline": [
            "Book Event",
            "Capture",
            "Upload",
            "Cull",
            "Edit",
            "Organize",
            "Publish Gallery",
            "Photo Search",
            "Download",
            "Share",
        ],
        "testimonials": [
            (
                "LumisPixel helps us deliver event galleries faster without losing track of important guest photos.",
                "Event photographer",
            ),
            (
                "Guests use selfie search instead of asking our team to find photos manually.",
                "Gala photographer",
            ),
            (
                "Our client galleries stay organized, and attendees leave happier with easy downloads.",
                "Studio owner",
            ),
        ],
        "metrics": [
            "Faster Organization",
            "Easy Guest Search",
            "More Sales",
            "One Connected Workflow",
        ],
        "faqs": [
            (
                "How does selfie photo search work?",
                "Guests upload a selfie when search is enabled. LumisPixel finds matching photos in the event gallery.",
            ),
            (
                "Can I create galleries for multiple events?",
                "Yes. Create separate galleries for conferences, galas, festivals, fundraisers, and private events.",
            ),
            (
                "Can guests download high-resolution photos?",
                "Yes. Photographers control download access for each gallery and package.",
            ),
            (
                "Can I sell prints and digital downloads?",
                "Yes. Sell prints and digital files directly from each gallery.",
            ),
            (
                "Can I organize attendees automatically?",
                "Yes. Face recognition helps group attendees across high-volume event galleries.",
            ),
            (
                "Which tools can LumisPixel replace?",
                "It can replace tools for editing, galleries, face search, websites, stores, messages, and analytics.",
            ),
        ],
    }
    return render(request, "event_photography.html", context)


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
                "text": "Too many photos to organize after each shoot.",
            },
            {
                "icon": "bi-chat-dots",
                "text": "Clients asking you to find their photos.",
            },
            {
                "icon": "bi-cloud-arrow-up",
                "text": "Hours lost uploading galleries and links.",
            },
            {
                "icon": "bi-bag-x",
                "text": "Missed print sales from disconnected buying.",
            },
            {
                "icon": "bi-grid-3x3-gap",
                "text": "Separate apps for galleries, websites, sales, and analytics.",
            },
            {
                "icon": "bi-search",
                "text": "Hard-to-search events, people, and moments.",
            },
            {
                "icon": "bi-window",
                "text": "A website that does not match your brand.",
            },
            {
                "icon": "bi-graph-up",
                "text": "Scattered insights across disconnected tools.",
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
                "copy": "Manage clients, events, billing, orders, analytics, and marketing from one calm workspace.",
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
                "copy": "Let clients find themselves, people, and moments without scrolling through every image.",
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
                "copy": "Speed up review with AI signals for quality issues, duplicates, and likely keepers.",
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
                "copy": "Deliver polished galleries clients can access, share, favorite, download, and buy from.",
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
                "copy": "Build a professional portfolio site that turns visitors into inquiries.",
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
                "copy": "Sell downloads, prints, albums, and offers directly from the gallery.",
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
                "copy": "See revenue, downloads, views, popular images, and client engagement in one place.",
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
                "copy": "Connect with requests, collaborators, second shooters, editors, and future client discovery.",
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
                "copy": "Style-aware edits and guided adjustments.",
            },
            {
                "status": "Future",
                "title": "AI Album Design",
                "copy": "Layouts based on story, emotion, and selections.",
            },
            {
                "status": "Future",
                "title": "Marketing Assistant",
                "copy": "Campaign ideas, email drafts, and sales prompts.",
            },
            {
                "status": "Future",
                "title": "Mobile App",
                "copy": "Studio and client access on the go.",
            },
            {
                "status": "Expanding",
                "title": "Marketplace",
                "copy": "Requests, collaborators, and discovery.",
            },
            {
                "status": "Future",
                "title": "Studio CRM",
                "copy": "Client history and pipeline management.",
            },
            {
                "status": "Future",
                "title": "Booking System",
                "copy": "Availability, deposits, packages, and scheduling.",
            },
            {
                "status": "Future",
                "title": "Smart Contracts",
                "copy": "Templates and guided agreements.",
            },
        ],
        "testimonials": [
            {
                "text": "It understands gallery delivery, client questions, and the chaos after a big event.",
                "role": "Placeholder testimonial — wedding photographer",
            },
            {
                "text": "Fewer tools, faster client discovery, and more ways to sell the work I already created.",
                "role": "Placeholder testimonial — sports photographer",
            },
            {
                "text": "My website, galleries, orders, and analytics should finally work together.",
                "role": "Placeholder testimonial — portrait studio owner",
            },
        ],
        "faqs": [
            {
                "q": "Can clients upload selfies?",
                "a": "Yes. Clients can use selfie-based discovery to find their images quickly in supported galleries.",
            },
            {
                "q": "Can I sell prints?",
                "a": "Yes. The sales vision includes prints, frames, albums, packages, downloads, coupons, and gift cards.",
            },
            {
                "q": "Can I use my own branding?",
                "a": "Yes. Websites and galleries support themes, branding, portfolios, SEO, and contact pages.",
            },
            {
                "q": "Can clients download photos?",
                "a": "Yes. Galleries support downloads with passwords, favorites, watermarks, QR codes, and event codes.",
            },
            {
                "q": "How does AI work?",
                "a": "AI powers search, face recognition, quality checks, blur and duplicate detection, tagging, smart collections, and future recommendations.",
            },
            {
                "q": "Can I migrate from another gallery provider?",
                "a": "Migration tools are planned. LumisPixel is being built for photographers replacing multiple disconnected tools.",
            },
            {
                "q": "What file formats are supported?",
                "a": "Final file-format support will be confirmed as upload and processing services are implemented.",
            },
            {
                "q": "How secure are my galleries?",
                "a": "Galleries are designed for passwords, event codes, watermarks, and controlled downloads. Production security depends on backend enforcement.",
            },
        ],
    }
    return render(request, "for_photographers.html", context)
