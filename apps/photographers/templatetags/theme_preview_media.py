from django import template

register = template.Library()


PRISM_FILTER_IMAGE = "img/photographers/theme-previews/Atelier/atelier-prism-creative-filters.webp"

THEME_PREVIEW_MEDIA = {
    "frame": {
        "hero": [
            "img/photographers/theme-previews/frame/frame-hero-wedding.webp",
            "img/photographers/theme-previews/frame/frame-graduation.webp",
            "img/photographers/theme-previews/frame/frame-family.webp",
            "img/photographers/theme-previews/frame/frame-birthday.webp",
            "img/photographers/theme-previews/frame/frame-studio-portrait.webp",
            "img/photographers/theme-previews/frame/frame-commercial.webp",
        ],
        "about": ["img/photographers/theme-previews/frame/frame-studio-portrait.webp"],
        "portfolio": [
            "img/photographers/theme-previews/frame/frame-graduation.webp",
            "img/photographers/theme-previews/frame/frame-family.webp",
            "img/photographers/theme-previews/frame/frame-birthday.webp",
            "img/photographers/theme-previews/frame/frame-studio-portrait.webp",
            "img/photographers/theme-previews/frame/frame-commercial.webp",
        ],
        "team": [
            "img/photographers/theme-previews/frame/frame-studio-portrait.webp",
            "img/photographers/theme-previews/frame/frame-commercial.webp",
            "img/photographers/theme-previews/frame/frame-family.webp",
            "img/photographers/theme-previews/frame/frame-graduation.webp",
        ],
        "equipment": [
            "img/photographers/theme-previews/Panorama/panorama-equipment-camera.webp",
            "img/photographers/theme-previews/Panorama/panorama-equipment-drone.webp",
            "img/photographers/theme-previews/Panorama/panorama-equipment-lighting.webp",
            "img/photographers/theme-previews/Panorama/panorama-equipment-reflector.webp",
            PRISM_FILTER_IMAGE,
            "img/photographers/theme-previews/Panorama/panorama-equipment-power-care.webp",
        ],
    },
    "narrative": {
        "hero": ["img/photographers/theme-previews/Narrative/narrative-hero-wedding.webp"],
        "about": ["img/photographers/theme-previews/Narrative/narrative-about-photographer.webp"],
        "portfolio": [
            "img/photographers/theme-previews/Narrative/narrative-wedding-celebration.webp",
            "img/photographers/theme-previews/Narrative/narrative-couple-lifestyle.webp",
            "img/photographers/theme-previews/Narrative/narrative-family.webp",
            "img/photographers/theme-previews/Narrative/narrative-editorial-portrait.webp",
            "img/photographers/theme-previews/Narrative/narrative-brand.webp",
        ],
        "team": [
            "img/photographers/theme-previews/Narrative/narrative-about-photographer.webp",
            "img/photographers/theme-previews/Narrative/narrative-brand.webp",
            "img/photographers/theme-previews/Narrative/narrative-editorial-portrait.webp",
            "img/photographers/theme-previews/Narrative/narrative-couple-lifestyle.webp",
        ],
        "equipment": [
            "img/photographers/theme-previews/Panorama/panorama-equipment-camera.webp",
            "img/photographers/theme-previews/Panorama/panorama-equipment-drone.webp",
            "img/photographers/theme-previews/Panorama/panorama-equipment-lighting.webp",
            "img/photographers/theme-previews/Panorama/panorama-equipment-reflector.webp",
            PRISM_FILTER_IMAGE,
            "img/photographers/theme-previews/Panorama/panorama-equipment-power-care.webp",
        ],
    },
    "panorama": {
        "hero": ["img/photographers/theme-previews/Panorama/panorama-commercial-campaign.webp"],
        "about": ["img/photographers/theme-previews/Panorama/panorama-editorial-portrait.webp"],
        "portfolio": [
            "img/photographers/theme-previews/Panorama/panorama-corporate-event.webp",
            "img/photographers/theme-previews/Panorama/panorama-architecture.webp",
            "img/photographers/theme-previews/Panorama/panorama-product.webp",
            "img/photographers/theme-previews/Panorama/panorama-wedding-barn.webp",
            "img/photographers/theme-previews/Panorama/panorama-editorial-portrait-alt.webp",
        ],
        "team": [
            "img/photographers/theme-previews/Panorama/panorama-editorial-portrait.webp",
            "img/photographers/theme-previews/Panorama/panorama-corporate-event.webp",
            "img/photographers/theme-previews/Panorama/panorama-editorial-portrait-alt.webp",
            "img/photographers/theme-previews/Panorama/panorama-commercial-campaign.webp",
        ],
        "equipment": [
            "img/photographers/theme-previews/Panorama/panorama-equipment-camera.webp",
            "img/photographers/theme-previews/Panorama/panorama-equipment-drone.webp",
            "img/photographers/theme-previews/Panorama/panorama-equipment-lighting.webp",
            "img/photographers/theme-previews/Panorama/panorama-equipment-reflector.webp",
            PRISM_FILTER_IMAGE,
            "img/photographers/theme-previews/Panorama/panorama-equipment-power-care.webp",
        ],
    },
    "monograph": {
        "hero": ["img/photographers/theme-previews/Monograph/monograph-hero-cinematic-editorial.webp"],
        "about": ["img/photographers/theme-previews/Monograph/monograph-about-photographer.webp"],
        "portfolio": [
            "img/photographers/theme-previews/Monograph/monograph-fashion-editorial.webp",
            "img/photographers/theme-previews/Monograph/monograph-fine-art-portrait.webp",
            "img/photographers/theme-previews/Monograph/monograph-fine-art-portrait-alt.webp",
            "img/photographers/theme-previews/Monograph/monograph-beauty-editorial.webp",
            "img/photographers/theme-previews/Monograph/monograph-monochrome-portrait.webp",
        ],
        "team": [
            "img/photographers/theme-previews/Monograph/monograph-about-photographer.webp",
            "img/photographers/theme-previews/Monograph/monograph-fashion-editorial.webp",
            "img/photographers/theme-previews/Monograph/monograph-beauty-editorial.webp",
            "img/photographers/theme-previews/Monograph/monograph-monochrome-portrait.webp",
        ],
        "equipment": [
            "img/photographers/theme-previews/Panorama/panorama-equipment-camera.webp",
            "img/photographers/theme-previews/Panorama/panorama-equipment-drone.webp",
            "img/photographers/theme-previews/Panorama/panorama-equipment-lighting.webp",
            "img/photographers/theme-previews/Panorama/panorama-equipment-reflector.webp",
            PRISM_FILTER_IMAGE,
            "img/photographers/theme-previews/Panorama/panorama-equipment-power-care.webp",
        ],
    },
    "collective": {
        "hero": ["img/photographers/theme-previews/Collective/collective-couple-city-session-wave.webp"],
        "about": ["img/photographers/theme-previews/Collective/collective-anniversary-dinner.webp"],
        "portfolio": [
            "img/photographers/theme-previews/Collective/collective-baby-shower.webp",
            "img/photographers/theme-previews/Collective/collective-graduation-family.webp",
            "img/photographers/theme-previews/Collective/collective-youth-soccer.webp",
            "img/photographers/theme-previews/Collective/collective-family-reunion-latina.webp",
            "img/photographers/theme-previews/Collective/collective-surprise-proposal-guests.webp",
        ],
        "team": [
            "img/photographers/theme-previews/Collective/collective-couple-city-session-wide.webp",
            "img/photographers/theme-previews/Collective/collective-birthday-backyard.webp",
            "img/photographers/theme-previews/Collective/collective-first-birthday-living-room.webp",
            "img/photographers/theme-previews/Collective/collective-family-reunion-poolside.webp",
        ],
        "equipment": [
            "img/photographers/theme-previews/Panorama/panorama-equipment-camera.webp",
            "img/photographers/theme-previews/Panorama/panorama-equipment-drone.webp",
            "img/photographers/theme-previews/Panorama/panorama-equipment-lighting.webp",
            "img/photographers/theme-previews/Panorama/panorama-equipment-reflector.webp",
            PRISM_FILTER_IMAGE,
            "img/photographers/theme-previews/Panorama/panorama-equipment-power-care.webp",
        ],
    },
    "atelier": {
        "hero": ["img/photographers/theme-previews/Atelier/atelier-hero-studio.webp"],
        "about": ["img/photographers/theme-previews/Atelier/atelier-about-photographer.webp"],
        "portfolio": [
            "img/photographers/theme-previews/Atelier/atelier-studio-fashion-shoot.webp",
            "img/photographers/theme-previews/Atelier/atelier-basketball-game.webp",
            "img/photographers/theme-previews/Atelier/atelier-corporate-portrait.webp",
            "img/photographers/theme-previews/Atelier/atelier-studio-production.webp",
            "img/photographers/theme-previews/Atelier/atelier-about-photographer.webp",
        ],
        "team": [
            "img/photographers/theme-previews/Atelier/atelier-about-photographer.webp",
            "img/photographers/theme-previews/Atelier/atelier-corporate-portrait.webp",
            "img/photographers/theme-previews/Atelier/atelier-studio-production.webp",
            "img/photographers/theme-previews/Atelier/atelier-studio-fashion-shoot.webp",
        ],
        "equipment": [
            "img/photographers/theme-previews/Panorama/panorama-equipment-camera.webp",
            "img/photographers/theme-previews/Panorama/panorama-equipment-drone.webp",
            "img/photographers/theme-previews/Panorama/panorama-equipment-lighting.webp",
            "img/photographers/theme-previews/Panorama/panorama-equipment-reflector.webp",
            PRISM_FILTER_IMAGE,
            "img/photographers/theme-previews/Panorama/panorama-equipment-power-care.webp",
        ],
    },
}

SHARED_REVIEW_MEDIA = {
    "background": "img/photographers/theme-previews/Reviews/reviews-background.webp",
    "clients": [
        "img/photographers/theme-previews/Reviews/reviews-client-wedding.webp",
        "img/photographers/theme-previews/Reviews/reviews-client-family.webp",
        "img/photographers/theme-previews/Reviews/reviews-client-brand.webp",
    ],
}


@register.simple_tag
def theme_media_list(theme_slug, section):
    return THEME_PREVIEW_MEDIA.get(theme_slug, {}).get(section, [])


@register.simple_tag
def theme_media(theme_slug, section, index=0):
    media = THEME_PREVIEW_MEDIA.get(theme_slug, {}).get(section, [])
    try:
        return media[int(index)]
    except (IndexError, TypeError, ValueError):
        return ""


@register.simple_tag
def review_background():
    return SHARED_REVIEW_MEDIA["background"]


@register.simple_tag
def review_client_image(index=0):
    try:
        return SHARED_REVIEW_MEDIA["clients"][int(index)]
    except (IndexError, TypeError, ValueError):
        return ""
