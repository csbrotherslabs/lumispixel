from django.shortcuts import render

from apps.core.views import public_page, add

add("ai_photo_search", "AI Photo Search", "Products", description="Explain LumisPixel AI photo discovery for faster gallery search and client self-service.")
add("ai_editing_culling", "AI Editing & Culling", "Products", description="Preview AI-assisted editing and culling workflows designed to reduce photographer production time.")


def editing_culling(request):
    context = {
        "pain_points": [
            ("Thousands of images", "Large shoots create full galleries before editing even starts."),
            ("Duplicate photos", "Near-identical frames make final selections harder to compare."),
            ("Slightly blurry shots", "Soft images can hide among otherwise strong moments."),
            ("Closed eyes", "Small expression issues often require careful manual review."),
            ("Similar poses", "Repeated compositions slow down confident keep-or-skip decisions."),
            ("Manual ratings", "Star ratings and flags take time across every event."),
            ("Endless scrolling", "Review fatigue builds before creative editing begins."),
        ],
        "assistant_features": [
            ("Quality Scoring", "Surface likely strong frames for faster review."),
            ("Blur Detection", "Flag soft images that may need closer inspection."),
            ("Duplicate Detection", "Group similar images so comparisons feel easier."),
            ("Closed Eyes Detection", "Highlight expression issues before client delivery."),
            ("Face Detection", "Help organize galleries around people and moments."),
            ("Auto Tagging", "Suggest labels that make collections easier to search."),
            ("Smart Collections", "Create helpful groupings for photographer review."),
            ("Semantic Search", "Find images by natural words and event context."),
            ("Batch Suggestions", "Recommend next steps while leaving approval to you."),
        ],
        "workflow": ["Import Photos", "AI Reviews Images", "Suggested Selections", "Photographer Reviews", "Edit", "Deliver Galleries"],
        "benefits": [
            ("bi-eye", "Review fewer photos manually", "Start with helpful signals instead of every frame."),
            ("bi-lightning-charge", "Find your best images faster", "Move likely keepers into focus sooner."),
            ("bi-arrow-repeat", "Reduce repetitive work", "Spend less energy on repeated sorting tasks."),
            ("bi-folder2-open", "Organize galleries efficiently", "Prepare cleaner sets for review and delivery."),
            ("bi-send-check", "Prepare deliveries sooner", "Shorten the path from shoot to gallery."),
            ("bi-people", "Spend more time with clients", "Protect more time for service and creativity."),
        ],
        "capabilities": [
            ("Image Quality Review", "Planned", "Assisted scoring to help prioritize image review."),
            ("Duplicate Identification", "Planned", "Suggested grouping for similar or repeated frames."),
            ("Blur Detection", "Planned", "Review signals for potentially soft photos."),
            ("Auto Organization", "Coming Soon", "Suggested gallery groupings and tags."),
            ("Semantic Search", "Future Release", "Search concepts, scenes, and moments with plain language."),
            ("Tag Suggestions", "Coming Soon", "Optional labels for easier discovery."),
        ],
        "roadmap": ["AI Color Matching", "AI Crop Suggestions", "AI Album Design", "AI Editing Presets", "AI Subject Selection", "AI Background Cleanup", "AI Skin Retouching", "AI Batch Enhancements"],
        "faqs": [
            ("Will AI edit my photos automatically?", "No. LumisPixel positions AI as optional assistance for review and organization, not automatic final editing."),
            ("Can I approve suggestions?", "Yes. Suggested selections and recommendations are intended for photographer review before anything moves forward."),
            ("Does AI delete photos?", "No. The workflow should not automatically delete images. Photographers remain responsible for final decisions."),
            ("Can I disable AI?", "AI assistance is intended to be optional, with photographer-controlled settings as features become available."),
            ("Does it support RAW images?", "RAW workflow details are still part of backend implementation planning and should be confirmed before launch."),
            ("Will AI improve over time?", "Yes. Future releases may improve recommendations while keeping photographer approval at the center."),
            ("Are these tools available today?", "This page describes planned and coming LumisPixel AI workflow capabilities, clearly labeled by readiness."),
            ("Can I choose which AI features to use?", "That is the goal: optional tools that photographers can enable based on their workflow."),
        ],
    }
    return render(request, "ai_editing_culling.html", context)


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
