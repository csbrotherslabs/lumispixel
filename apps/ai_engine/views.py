from django.shortcuts import render

from apps.core.views import public_page, add

add("ai_photo_search", "AI Photo Search", "Products", description="Explain LumisPixel AI photo discovery for faster gallery search and client self-service.")
add("ai_editing_culling", "AI Editing & Culling", "Products", description="Preview AI-assisted editing and culling workflows designed to reduce photographer production time.")


def ai_photo_search(request):
    context = {
        "pain_points": [
            {"icon": "bi-images", "text": "Scroll through thousands of images"},
            {"icon": "bi-person-bounding-box", "text": "Hope you recognize yourself"},
            {"icon": "bi-chat-dots", "text": "Ask the photographer for help"},
            {"icon": "bi-heartbreak", "text": "Miss important memories"},
            {"icon": "bi-hourglass-split", "text": "Spend far too much time searching"},
        ],
        "selfie_steps": [
            "Upload Selfie",
            "AI Searches the Gallery",
            "Matching Photos",
            "Review Results",
            "Download or Order",
        ],
        "event_types": [
            ("Wedding", "bi-heart"), ("Graduation", "bi-mortarboard"),
            ("Youth Sports", "bi-trophy"), ("Corporate Events", "bi-briefcase"),
            ("Festivals", "bi-music-note-beamed"), ("School Pictures", "bi-building"),
            ("Conferences", "bi-mic"), ("Family Reunions", "bi-people"),
            ("Marathons", "bi-stopwatch"), ("Portrait Sessions", "bi-person-square"),
            ("Community Events", "bi-calendar-event"), ("Travel", "bi-airplane"),
        ],
        "benefits": [
            ("Less scrolling", "Start with likely matches instead of every image."),
            ("Find photos faster", "Quickly narrow large galleries when search is enabled."),
            ("View likely matches", "Review suggested photos and choose the ones you love."),
            ("Save favorites", "Keep your best memories together for easy return visits."),
            ("Share memories", "Send favorite moments to family and friends when available."),
            ("Enjoy your gallery", "Spend less time searching and more time reliving the day."),
        ],
        "comparison": [
            {"traditional": "Browse folders", "lumis": "Upload selfie"},
            {"traditional": "Scroll endlessly", "lumis": "AI narrows results"},
            {"traditional": "Ask photographer", "lumis": "Review likely matches"},
            {"traditional": "Lose time", "lumis": "Save favorites"},
            {"traditional": "Manual searching", "lumis": "Enjoy your memories"},
        ],
        "privacy_cards": [
            ("Photographer Controlled", "Selfie search is available only when enabled by the photographer."),
            ("Gallery Specific", "Searches are performed only within the selected gallery or event."),
            ("Your Choice", "Clients choose whether to use selfie search."),
            ("Designed for Simplicity", "The goal is to help reduce time spent searching through large galleries."),
        ],
        "privacy_points": [
            "Photographer controls availability",
            "Private galleries",
            "Optional selfie search",
            "Temporary processing",
            "Client-controlled search",
        ],
        "example_steps": [
            "Attend wedding", "Photographer uploads gallery", "Receive gallery link",
            "Upload selfie", "Review likely matches", "Download favorites", "Share with family",
        ],
        "faqs": [
            ("How does selfie search work?", "Upload a clear selfie in a supported gallery. LumisPixel uses it to help surface likely matching photos."),
            ("Do I need an account?", "Some galleries may require an account, password, private link, or event code depending on photographer settings."),
            ("Will AI always find every photo?", "No. AI Photo Search is designed to help narrow results, but matches can vary by image quality and gallery settings."),
            ("Can I upload another selfie?", "When selfie search is available, you may be able to try another clear photo to improve likely matches."),
            ("Who can use selfie search?", "Clients and guests can use it when the photographer enables the feature for the selected gallery."),
            ("Are my selfies stored?", "Selfies are used to help search the selected gallery. Final retention controls may depend on production settings."),
            ("Can photographers disable this feature?", "Yes. Feature availability depends on gallery settings controlled by the photographer."),
            ("Can I search multiple events?", "Search is intended for the selected gallery or event. Use each gallery link or event access separately."),
        ],
    }
    return render(request, "ai_photo_search.html", context)
