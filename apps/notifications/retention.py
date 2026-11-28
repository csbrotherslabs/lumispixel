"""Opt-in terminal payload retention. Preserve provider and audit evidence."""
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import EmailDelivery

@transaction.atomic
def purge_old_terminal_payloads(limit=200):
    days = getattr(settings, "EMAIL_TERMINAL_PAYLOAD_RETENTION_DAYS", 0)
    if days <= 0:
        return 0
    now = timezone.now()
    cutoff = now-timedelta(days=days)
    # Only accepted submissions with a reliable terminal timestamp.
    rows = list(EmailDelivery.objects.select_for_update(skip_locked=True).filter(
        status=EmailDelivery.Status.SENT, sent_at__lte=cutoff,
        payload_purged_at__isnull=True).order_by("sent_at", "pk")[:limit])
    for row in rows:
        row.subject = "[redacted]"
        row.plain_body = row.html_body = row.encrypted_payload = ""
        row.lifecycle_context = {}
        row.payload_purged_at = now
        row.save(update_fields=["subject", "plain_body", "html_body", "encrypted_payload",
            "lifecycle_context", "payload_purged_at"])
    return len(rows)
