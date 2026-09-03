from django import template

register = template.Library()


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
        "portfolio": [
            "img/photographers/theme-previews/frame/frame-graduation.webp",
            "img/photographers/theme-previews/frame/frame-family.webp",
            "img/photographers/theme-previews/frame/frame-birthday.webp",
            "img/photographers/theme-previews/frame/frame-studio-portrait.webp",
            "img/photographers/theme-previews/frame/frame-commercial.webp",
        ],
    },
    "narrative": {
        "hero": ["img/photographers/theme-previews/narrative/narrative-hero-wedding.webp"],
        "about": ["img/photographers/theme-previews/narrative/narrative-about-photographer.webp"],
        "portfolio": [
            "img/photographers/theme-previews/narrative/narrative-wedding-celebration.webp",
            "img/photographers/theme-previews/narrative/narrative-couple-lifestyle.webp",
            "img/photographers/theme-previews/narrative/narrative-family.webp",
            "img/photographers/theme-previews/narrative/narrative-editorial-portrait.webp",
            "img/photographers/theme-previews/narrative/narrative-brand.webp",
        ],
    },
    "panorama": {
        "hero": ["img/photographers/theme-previews/panorama/panorama-commercial-campaign.webp"],
        "about": ["img/photographers/theme-previews/panorama/panorama-editorial-portrait.webp"],
        "portfolio": [
            "img/photographers/theme-previews/panorama/panorama-corporate-event.webp",
            "img/photographers/theme-previews/panorama/panorama-architecture.webp",
            "img/photographers/theme-previews/panorama/panorama-product.webp",
            "img/photographers/theme-previews/panorama/panorama-wedding-barn.webp",
            "img/photographers/theme-previews/panorama/panorama-editorial-portrait-alt.webp",
        ],
        "equipment": [
            "img/photographers/theme-previews/panorama/panorama-equipment-camera.webp",
            "img/photographers/theme-previews/panorama/panorama-equipment-drone.webp",
            "img/photographers/theme-previews/panorama/panorama-equipment-lighting.webp",
            "img/photographers/theme-previews/panorama/panorama-equipment-reflector.webp",
            "img/photographers/theme-previews/monograph/monograph-equipment-prism-filters.webp",
            "img/photographers/theme-previews/panorama/panorama-equipment-power-care.webp",
        ],
    },
    "monograph": {
        "hero": ["img/photographers/theme-previews/monograph/monograph-hero-cinematic-editorial.webp"],
        "about": ["img/photographers/theme-previews/monograph/monograph-about-photographer.webp"],
        "portfolio": [
            "img/photographers/theme-previews/monograph/monograph-fashion-editorial.webp",
            "img/photographers/theme-previews/monograph/monograph-fine-art-portrait.webp",
            "img/photographers/theme-previews/monograph/monograph-fine-art-portrait-alt.webp",
            "img/photographers/theme-previews/monograph/monograph-beauty-editorial.webp",
            "img/photographers/theme-previews/monograph/monograph-monochrome-portrait.webp",
        ],
        "equipment": [
            "img/photographers/theme-previews/panorama/panorama-equipment-camera.webp",
            "img/photographers/theme-previews/panorama/panorama-equipment-drone.webp",
            "img/photographers/theme-previews/panorama/panorama-equipment-lighting.webp",
            "img/photographers/theme-previews/panorama/panorama-equipment-reflector.webp",
            "img/photographers/theme-previews/monograph/monograph-equipment-prism-filters.webp",
            "img/photographers/theme-previews/panorama/panorama-equipment-power-care.webp",
        ],
    },
    "collective": {
        "hero": ["img/photographers/theme-previews/collective/collective-couple-city-session-wave.webp"],
        "about": ["img/photographers/theme-previews/collective/collective-anniversary-dinner.webp"],
        "portfolio": [
            "img/photographers/theme-previews/collective/collective-baby-shower.webp",
            "img/photographers/theme-previews/collective/collective-graduation-family.webp",
            "img/photographers/theme-previews/collective/collective-youth-soccer.webp",
            "img/photographers/theme-previews/collective/collective-family-reunion-latina.webp",
            "img/photographers/theme-previews/collective/collective-surprise-proposal-guests.webp",
        ],
        "team": [
            "img/photographers/theme-previews/collective/collective-couple-city-session-wide.webp",
            "img/photographers/theme-previews/collective/collective-birthday-backyard.webp",
            "img/photographers/theme-previews/collective/collective-first-birthday-living-room.webp",
            "img/photographers/theme-previews/collective/collective-family-reunion-poolside.webp",
        ],
    },
    "atelier": {
        "hero": ["img/photographers/theme-previews/atelier/atelier-hero-studio.webp"],
        "portfolio": [
            "img/photographers/theme-previews/atelier/atelier-studio-fashion-shoot.webp",
            "img/photographers/theme-previews/panorama/panorama-commercial-campaign.webp",
            "img/photographers/theme-previews/panorama/panorama-corporate-event.webp",
            "img/photographers/theme-previews/panorama/panorama-architecture.webp",
            "img/photographers/theme-previews/panorama/panorama-product.webp",
        ],
        "team": [
            "img/photographers/theme-previews/atelier/atelier-about-photographer.webp",
            "img/photographers/theme-previews/atelier/atelier-corporate-portrait.webp",
            "img/photographers/theme-previews/atelier/atelier-basketball-game.webp",
            "img/photographers/theme-previews/atelier/atelier-studio-production.webp",
        ],
        "equipment": [
            "img/photographers/theme-previews/panorama/panorama-equipment-camera.webp",
            "img/photographers/theme-previews/panorama/panorama-equipment-drone.webp",
            "img/photographers/theme-previews/panorama/panorama-equipment-lighting.webp",
            "img/photographers/theme-previews/panorama/panorama-equipment-reflector.webp",
            "img/photographers/theme-previews/monograph/monograph-equipment-prism-filters.webp",
            "img/photographers/theme-previews/panorama/panorama-equipment-power-care.webp",
        ],
    },
}

SHARED_REVIEW_MEDIA = {
    "background": "img/photographers/theme-previews/reviews/reviews-background.webp",
    "clients": [
        "img/photographers/theme-previews/reviews/reviews-client-wedding.webp",
        "img/photographers/theme-previews/reviews/reviews-client-family.webp",
        "img/photographers/theme-previews/reviews/reviews-client-brand.webp",
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
