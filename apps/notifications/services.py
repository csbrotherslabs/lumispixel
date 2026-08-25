from .models import Notification


def notify_user(*, recipient, title, message, category=Notification.Category.SYSTEM, action_url="", action_label="", metadata=None):
    """Create an inbox notification for one user."""
    return Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        category=category,
        action_url=action_url,
        action_label=action_label,
        metadata=metadata or {},
    )
