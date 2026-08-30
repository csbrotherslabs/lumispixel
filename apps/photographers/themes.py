from copy import deepcopy


SECTION_LIBRARY = {
    "hero": {"name": "Hero", "description": "Opening image, positioning statement, and primary action."},
    "about": {"name": "About", "description": "The photographer or studio story."},
    "services": {"name": "Services", "description": "Photography specialties and client offerings."},
    "portfolio": {"name": "Selected work", "description": "A curated project and portfolio presentation."},
    "stats": {"name": "Experience", "description": "Selected business and experience highlights."},
    "team": {"name": "Team", "description": "Photographers, editors, and studio collaborators."},
    "reviews": {"name": "Ratings & reviews", "description": "Verified LumisPixel client feedback."},
    "availability": {"name": "Availability", "description": "Privacy-safe public dates connected to your LumisPixel schedule."},
    "equipment": {"name": "Equipment & capabilities", "description": "A carousel showing the professional tools behind your work."},
    "contact": {"name": "Contact", "description": "A clear inquiry and booking call to action."},
}


THEME_DEFINITIONS = {
    "basic": {
        "slug": "frame",
        "name": "Frame",
        "source": "kimono_main/dark/index-21.html",
        "preview_template": "photographers/theme_previews/frame.html",
        "best_for": "Minimal portfolios and visual storytellers",
        "description": "A focused, image-led experience with cinematic navigation and very little distraction.",
        "preview_class": "is-frame",
        "sections": ["hero", "portfolio", "contact"],
        "accent": "#df1f26",
    },
    "elegant": {
        "slug": "narrative",
        "name": "Narrative",
        "source": "kimono_main/dark/index-19.html",
        "preview_template": "photographers/theme_previews/narrative.html",
        "best_for": "Wedding, lifestyle, and full-service studios",
        "description": "A complete agency-style story with services, work, proof, and a strong inquiry path.",
        "preview_class": "is-narrative",
        "sections": ["hero", "services", "about", "portfolio", "stats", "reviews", "contact"],
        "accent": "#e34e42",
    },
    "modern_studio": {
        "slug": "panorama",
        "name": "Panorama",
        "source": "kimono_main/dark/index-15.html",
        "preview_template": "photographers/theme_previews/panorama.html",
        "best_for": "Studios with broad services and project depth",
        "description": "A wide, editorial presentation with service discovery and layered project storytelling.",
        "preview_class": "is-panorama",
        "sections": ["hero", "services", "about", "equipment", "portfolio", "reviews", "contact"],
        "accent": "#d7ad78",
    },
    "cinematic": {
        "slug": "monograph",
        "name": "Monograph",
        "source": "kimono_main/dark/index-5.html",
        "preview_template": "photographers/theme_previews/monograph.html",
        "best_for": "Portrait, fashion, and fine-art portfolios",
        "description": "Bold typography, strong image rhythm, and a concise studio narrative.",
        "preview_class": "is-monograph",
        "sections": ["hero", "about", "services", "equipment", "portfolio", "reviews", "contact"],
        "accent": "#ec4b42",
    },
    "portfolio_editorial": {
        "slug": "collective",
        "name": "Collective",
        "source": "kimono_main/dark/index-5.html",
        "preview_template": "photographers/theme_previews/collective.html",
        "best_for": "Creative teams and multi-photographer brands",
        "description": "The Monograph foundation rebuilt around people, collaboration, and selected work.",
        "preview_class": "is-collective",
        "sections": ["hero", "portfolio", "about", "team", "reviews", "contact"],
        "accent": "#cbff3f",
    },
    "sports_events": {
        "slug": "atelier",
        "name": "Atelier",
        "source": "kimono_main/dark/index-15.html",
        "preview_template": "photographers/theme_previews/atelier.html",
        "best_for": "Established studios with services, teams, and scale",
        "description": "The Panorama foundation expanded with studio milestones and a visible team.",
        "preview_class": "is-atelier",
        "sections": ["hero", "services", "equipment", "stats", "portfolio", "reviews", "team", "contact"],
        "accent": "#ff5b4d",
    },
}


DEMO_CONTENT = {
    "brand": "North & Pine Studio",
    "eyebrow": "Photography / Film / Direction",
    "headline": "Stories shaped by light, movement, and honest connection.",
    "intro": "A Kansas City photography studio creating considered imagery for people, celebrations, and ambitious brands.",
    "services": [
        {"name": "Wedding Photography", "description": "Honest, artful coverage shaped around the people and moments that make the day yours.", "icon": "bi-camera"},
        {"name": "Wedding Films", "description": "Cinematic highlight films that preserve movement, voices, and the feeling of the celebration.", "icon": "bi-camera-reels"},
        {"name": "Portrait Sessions", "description": "Relaxed portrait experiences for individuals, couples, families, and creative professionals.", "icon": "bi-person-bounding-box"},
        {"name": "Event Coverage", "description": "Thoughtful visual storytelling for gatherings, launches, performances, and milestone events.", "icon": "bi-calendar-event"},
        {"name": "Editorial Stories", "description": "Concept-led photography with an expressive point of view for publications and campaigns.", "icon": "bi-journal-richtext"},
        {"name": "Brand Photography", "description": "Purposeful imagery for products, teams, and brands that need a clear visual identity.", "icon": "bi-stars"},
    ],
    "rating": "4.9",
    "review_count": "128",
    "review": "The photographs feel like us—beautiful, unforced, and full of the moments we thought nobody noticed.",
    "reviewer": "Maya & Jordan",
    "reviews": [
        {"quote": "The photographs feel like us—beautiful, unforced, and full of the moments we thought nobody noticed.", "name": "Maya & Jordan", "location": "Kansas City", "image": "img/testimonial/4.jpg"},
        {"quote": "From the first conversation to the final gallery, every detail felt thoughtful. We will treasure these images for years.", "name": "Olivia & Marcus", "location": "Chicago", "image": "img/testimonial/5.jpg"},
        {"quote": "The team made everyone comfortable and turned a fast-moving celebration into a collection that feels effortless and alive.", "name": "Avery Collins", "location": "New York", "image": "img/testimonial/6.jpg"},
    ],
    "stats": [("12+", "Years creating"), ("480", "Stories delivered"), ("18", "Awards & features")],
    "team": [
        ("Amara Reed", "Creative Director", "img/team/1.jpg"),
        ("Noah Bennett", "Lead Photographer", "img/team/2.jpg"),
        ("Mila Chen", "Editor", "img/team/3.jpg"),
        ("Elias Morgan", "Associate Photographer", "img/team/4.jpg"),
    ],
    "equipment": [
        {"name": "Dual-card camera", "description": "Immediate in-camera backup protects every important frame as it is captured.", "icon": "bi-camera"},
        {"name": "Professional drone", "description": "Elevated aerial photography and cinematic footage for a wider visual story.", "icon": "bi-airplane"},
        {"name": "Portable lighting", "description": "Reliable, flattering light for portraits, products, and changing environments.", "icon": "bi-lightbulb"},
        {"name": "5-in-1 reflector", "description": "Natural-looking light control indoors, outdoors, and everywhere between.", "icon": "bi-brightness-high"},
        {"name": "Prism & creative filters", "description": "Expressive editorial effects created intentionally in-camera.", "icon": "bi-triangle"},
        {"name": "Power & care kit", "description": "Spare batteries, air blower, and lens tools keep long assignments moving.", "icon": "bi-battery-charging"},
    ],
    "images": ["img/slider/30.jpg", "img/slider/22.jpg", "img/slider/28.jpg", "img/slider/32.jpg", "img/slider/17.jpg", "img/slider/45.jpg"],
}


def theme_options():
    options = []
    for value, definition in THEME_DEFINITIONS.items():
        item = deepcopy(definition)
        item["value"] = value
        item["included_sections"] = [SECTION_LIBRARY[key]["name"] for key in definition["sections"]]
        options.append(item)
    return options


def theme_by_slug(slug):
    return next((dict(value=value, **definition) for value, definition in THEME_DEFINITIONS.items() if definition["slug"] == slug or value.replace("_", "-") == slug), None)


def section_options():
    return [dict(key=key, **definition) for key, definition in SECTION_LIBRARY.items()]
