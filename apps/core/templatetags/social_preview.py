import random

from django import template
from django.templatetags.static import static
from django.urls import reverse

register = template.Library()

HOMEPAGE_IMAGES = (
    "hero-ai-photography-platform-mobile",
    "hero-client-photo-discovery-mobile",
    "hero-photographer-marketplace-mobile",
    "hero-photographer-workspace-mobile",
)


@register.simple_tag(takes_context=True)
def social_preview(context, gallery=None):
    """Expose only the selected cover, never gallery photos or invitation tokens."""
    request = context.get("request")
    if request is None:
        # Django's default 500 handler renders without request context.
        return {
            "title": "LumisPixel — Create. Deliver. Grow.",
            "description": "Galleries, clients, bookings—one workspace.",
            "image": "",
            "image_alt": "LumisPixel photography platform",
            "url": "",
        }
    image_name = HOMEPAGE_IMAGES[0]
    if gallery is None and request.path == reverse("core:index"):
        variant = request.GET.get("preview", "")
        image_name = HOMEPAGE_IMAGES[int(variant) - 1] if variant in ("1", "2", "3", "4") else random.choice(HOMEPAGE_IMAGES)
    try:
        image = static(f"img/social/{image_name}-share-v1.jpg")
    except ValueError:
        # A missing manifest entry must not take down an otherwise valid page.
        image = ""
    url = request.build_absolute_uri(request.path)
    title = "LumisPixel — Create. Deliver. Grow."
    description = "Galleries, clients, bookings—one workspace."
    image_alt = "LumisPixel photography platform"
    if gallery is not None:
        title = f"{gallery.name} | LumisPixel"
        description = "View your photography gallery on LumisPixel."
        url = request.build_absolute_uri(reverse("galleries:stable_gallery_access", args=[gallery.public_id]))
        if gallery.cover_image:
            image = gallery.cover_image.url
            image_alt = f"Cover of {gallery.name}"
    elif request.path == reverse("core:index") and request.GET.get("preview") in ("1", "2", "3", "4"):
        url += "?preview=" + request.GET["preview"]
    return {
        "title": title,
        "description": description,
        "image": request.build_absolute_uri(image) if image else "",
        "image_alt": image_alt,
        "url": url,
    }
