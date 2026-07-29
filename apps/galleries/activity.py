from .models import GalleryActivity


def log_gallery_activity(*, gallery, event_type, title=None, description="", actor=None,
                         actor_type=None, related_object=None, metadata=None):
    """Record a consistently scoped gallery event without storing request secrets."""
    if actor_type is None:
        actor_type = (GalleryActivity.ActorType.PHOTOGRAPHER if actor and actor.is_authenticated
                      else GalleryActivity.ActorType.SYSTEM)
    event = GalleryActivity(
        photographer=gallery.photographer, gallery=gallery, actor=actor if actor and actor.is_authenticated else None,
        actor_type=actor_type, event_type=event_type,
        title=title or dict(GalleryActivity.EventType.choices).get(event_type, event_type.replace("_", " ").title()),
        description=description,
        related_object_type=related_object._meta.verbose_name.title() if related_object else "Gallery",
        related_object_id=str(related_object.pk if related_object else gallery.pk), metadata=metadata or {},
    )
    event.full_clean()
    event.save()
    return event
