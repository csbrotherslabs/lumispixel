from django.shortcuts import render

from apps.core.views import add

add("client_galleries", "Client Galleries", "Products", description="Present polished online galleries for delivering, sharing, favoriting, and selling photography.")


def client_galleries(request):
    context = {
        "features": [
            ("Beautiful layouts", "Elegant presentation keeps the focus on each photograph."),
            ("Fast browsing", "Designed for smooth movement through large moments."),
            ("Favorites", "Clients can save selections when enabled by the photographer."),
            ("Private sharing", "Share access with family using photographer-approved settings."),
            ("High-resolution previews", "Present images with a polished, premium viewing feel."),
            ("Photographer branding", "Keep delivery aligned with your studio identity."),
            ("Responsive viewing", "Galleries adapt across desktop, tablet, and mobile."),
        ],
        "journey": ["Photographer Uploads Photos", "Gallery Created", "Client Receives Link", "Browse Photos", "Save Favorites", "Download Available Images", "Order Prints", "Share Memories"],
        "device_points": ["Responsive galleries", "Touch-friendly browsing", "Fast loading", "Consistent experience"],
        "client_needs": ["Favorites", "Slideshows", "Downloads", "Albums", "Collections", "Sharing", "QR Codes", "Password Protection", "Photographer branding"],
        "controls": ["Private galleries", "Password protection", "Download permissions", "Print products", "Gallery expiration", "Branding", "Watermarks", "Event organization"],
        "sharing": ["Private links", "Family sharing", "QR codes", "Favorites collections", "Social sharing where appropriate", "Simple navigation"],
        "occasions": [
            ("Wedding", "bi-heart"), ("Graduation", "bi-mortarboard"), ("Sports", "bi-trophy"), ("School", "bi-book"),
            ("Corporate", "bi-briefcase"), ("Portrait", "bi-person-square"), ("Family", "bi-people"), ("Real Estate", "bi-house"),
            ("Events", "bi-calendar-event"), ("Commercial", "bi-badge-ad"), ("Travel", "bi-airplane"), ("Festivals", "bi-music-note-beamed"),
        ],
        "comparison": [("Email attachments", "Beautiful online gallery"), ("USB drives", "Easy browsing"), ("Multiple folders", "Favorites"), ("Large ZIP files", "Photo search when enabled"), ("Confusing downloads", "Downloads when available"), ("One-time handoff", "Sharing and premium revisit experience")],
        "story_steps": ["Event Completed", "Photographer Curates the Gallery", "Client Receives Their Private Gallery", "Favorite the Best Moments", "Download or Order Keepsakes", "Share with Family and Friends", "Revisit Memories Anytime"],
        "customization": [
            ("Photographer branding", "Display your logo and business identity throughout the gallery."),
            ("Personalized Cover Images", "Create a welcoming first impression with a custom gallery cover."),
            ("Event Organization", "Organize galleries by weddings, sports, portraits, schools, corporate events, and more."),
            ("Flexible Layouts", "Present photos in clean layouts designed for viewing and discovery."),
            ("Client Experience", "Provide intuitive browsing across desktop, tablet, and mobile devices."),
            ("Gallery Controls", "Customize downloads, favorites, sharing, and products based on your workflow."),
        ],
        "faqs": [
            ("Do I need an account?", "Some galleries may require an account, password, private link, or event code depending on photographer settings."),
            ("Can I download photos?", "Downloads are available when enabled by the photographer and depending on gallery settings."),
            ("Can I order prints?", "Print ordering may be available when the photographer offers products for that gallery."),
            ("Can I share my gallery?", "Sharing options depend on the privacy and access settings selected by the photographer."),
            ("Can galleries be password protected?", "LumisPixel is designed to support private and password-protected gallery experiences."),
            ("Can I view galleries on my phone?", "Yes. Galleries are designed for responsive viewing across modern devices."),
            ("Can photographers customize galleries?", "Photographers can shape branding, access, downloads, products, and other options as supported by their workflow."),
            ("How long will galleries remain available?", "Availability depends on the photographer’s gallery settings, expiration choices, and delivery workflow."),
        ],
    }
    return render(request, "client_galleries.html", context)
