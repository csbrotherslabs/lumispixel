"""Authenticated Brevo transactional email callbacks."""
import hashlib
import hmac
import json
import re

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import BrevoEmailEvent, EmailDelivery

EVENTS = {"request", "delivered", "deferred", "soft_bounce", "hard_bounce",
          "blocked", "invalid_email", "error", "spam", "unsubscribed"}
ACCEPTED = {"request", "delivered"}
MAX_BODY = 256 * 1024


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def parse_event(payload):
    if not isinstance(payload, dict):
        raise ValueError("Expected object")
    event = payload.get("event")
    if not isinstance(event, str):
        raise ValueError("Missing event")
    if event not in EVENTS:
        return None
    recipient = payload.get("email")
    message_id = payload.get("message-id")
    stamp = payload.get("ts_epoch") or payload.get("ts_event") or payload.get("ts")
    if not isinstance(recipient, str) or not 1 <= len(recipient) <= 320:
        raise ValueError("Invalid recipient")
    if not isinstance(message_id, str) or not 1 <= len(message_id) <= 255:
        raise ValueError("Invalid message ID")
    if isinstance(stamp, bool) or not isinstance(stamp, (int, str)):
        raise ValueError("Invalid timestamp")
    stamp = int(stamp)
    if not 0 < stamp < 10**15:
        raise ValueError("Invalid timestamp")
    if stamp < 10**11:
        stamp *= 1000
    recipient = recipient.strip().casefold()
    token = payload.get("X-Mailin-custom", "")
    key = token[3:] if isinstance(token, str) and re.fullmatch(r"lp:[0-9a-f]{64}", token) else None
    return event, recipient, message_id, stamp, key


def persist_event(parsed):
    event, recipient, message_id, stamp, key = parsed
    recipient_hash = digest(recipient)
    fingerprint = digest(json.dumps([event, recipient_hash, message_id, stamp], separators=(",", ":")))
    delivery = EmailDelivery.objects.select_for_update().filter(idempotency_key=key).first() if key else None
    if delivery and recipient not in {r.strip().casefold() for r in delivery.recipients}:
        delivery = None
    record, created = BrevoEmailEvent.objects.get_or_create(fingerprint=fingerprint, defaults={
        "delivery": delivery, "event": event, "provider_message_id": message_id,
        "recipient_hash": recipient_hash, "occurred_at": stamp,
    })
    if not created or not delivery:
        return
    if event in ACCEPTED and delivery.status in (EmailDelivery.Status.SENDING, EmailDelivery.Status.UNCERTAIN):
        expected = {digest(r.strip().casefold()) for r in delivery.recipients}
        accepted = set(delivery.brevo_events.filter(event__in=ACCEPTED).values_list("recipient_hash", flat=True))
        if expected and expected <= accepted:
            delivery.status = EmailDelivery.Status.SENT
            delivery.sent_at = timezone.now()
            delivery.next_attempt_at = None
            delivery.last_error = ""
            delivery.failure_kind = ""
            delivery.save(update_fields=["status", "sent_at", "next_attempt_at", "last_error", "failure_kind"])


@csrf_exempt
@require_POST
def brevo_transactional(request):
    secret = getattr(settings, "BREVO_WEBHOOK_TOKEN", "")
    if not secret:
        return JsonResponse({"error": "Webhook unavailable"}, status=503)
    if not hmac.compare_digest(request.headers.get("Authorization", "").encode(), ("Bearer " + secret).encode()):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    if request.content_type != "application/json":
        return JsonResponse({"error": "Expected JSON"}, status=415)
    if len(request.body) > MAX_BODY:
        return JsonResponse({"error": "Payload too large"}, status=413)
    try:
        payload = json.loads(request.body)
        batch = payload if isinstance(payload, list) else [payload]
        if not 1 <= len(batch) <= 100:
            raise ValueError("Invalid batch")
        parsed = [parse_event(item) for item in batch]
    except (ValueError, TypeError, UnicodeError):
        return JsonResponse({"error": "Invalid event payload"}, status=400)
    with transaction.atomic():
        for item in parsed:
            if item is not None:
                persist_event(item)
    return JsonResponse({"ok": True})
