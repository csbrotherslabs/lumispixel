"""Persisted, studio-scoped setup progress for workspace owners."""
from django.urls import reverse

from apps.clients.models import Client, ClientSession
from apps.galleries.models import GalleryActivity, GalleryPhoto


def build_onboarding(access):
    if access.membership is not None:
        return None
    studio = access.studio
    shared = GalleryActivity.objects.filter(
        photographer=studio,
        event_type__in=[GalleryActivity.EventType.GALLERY_SHARED,
                        GalleryActivity.EventType.CLIENT_INVITED],
    ).exists()
    definitions = [
        ("Add a client", "Keep their details in one place.", "bi-person-plus",
         "add_client", Client.objects.filter(photographer=studio).exists()),
        ("Create a booking", "Plan your first session.", "bi-calendar-plus",
         "bookings", ClientSession.objects.filter(photographer=studio).exists()),
        ("Upload photos", "Build your first gallery.", "bi-cloud-arrow-up",
         "gallery_upload_queue", GalleryPhoto.objects.filter(
             gallery__photographer=studio, status=GalleryPhoto.Status.COMPLETED,
         ).exists()),
        ("Share a gallery", "Deliver photos to your client.", "bi-share",
         "galleries", shared),
    ]
    steps = [
        {"title": title, "description": description, "icon": icon,
         "url": reverse(f"photographer_workspace:{route}"), "complete": complete}
        for title, description, icon, route, complete in definitions
    ]
    next_step = next((step for step in steps if not step["complete"]), None)
    if next_step:
        next_step["current"] = True
    return {"steps": steps, "completed": sum(step["complete"] for step in steps),
            "next_step": next_step, "complete": next_step is None,
            "storage_key": f"lp-onboarding-dismissed:{studio.pk}"}
