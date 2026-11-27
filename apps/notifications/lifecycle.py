"""Lifecycle checks for queued email; never claim recall of an external submission."""
from django.db import transaction, models
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import EmailDelivery

QUEUED = (EmailDelivery.Status.PENDING, EmailDelivery.Status.RETRY)
TERMINAL = (EmailDelivery.Status.SENT, EmailDelivery.Status.DEAD, EmailDelivery.Status.FAILED,
            EmailDelivery.Status.CANCELLED, EmailDelivery.Status.EXPIRED)


def eligible(delivery):
    """Explicit allowlist of domain checks; unknown kinds fail closed."""
    if not delivery.lifecycle_kind:
        return not delivery.sensitive
    if delivery.lifecycle_kind == "gallery.invite":
        from apps.galleries.models import AccessToken, Gallery, GalleryInvitation, GalleryPermission
        token = AccessToken.objects.select_related("invitation__gallery").filter(
            pk=delivery.lifecycle_context.get("token_id"),
            invitation_id=delivery.lifecycle_context.get("invitation_id"),
            revoked_at__isnull=True).first()
        if not token:
            return False
        invitation, gallery = token.invitation, token.invitation.gallery
        now = timezone.now()
        return (
            invitation.status in (GalleryInvitation.Status.PENDING, GalleryInvitation.Status.ACTIVE)
            and not gallery.deleted_at and not gallery.archived_at
            and gallery.status in (Gallery.Status.PUBLISHED, Gallery.Status.DELIVERED)
            and (not token.expires_at or token.expires_at > now)
            and (not gallery.expires_at or gallery.expires_at > now)
            and not GalleryPermission.objects.filter(gallery=gallery, view_gallery=False).exists()
            and [email.casefold() for email in delivery.recipients] == [invitation.email.casefold()]
        )
    if delivery.lifecycle_kind in ("contract.review", "contract.signed"):
        from apps.clients.models import Contract, ContractPhotographerSignature, ContractSignature
        from apps.clients.contracts import _content_hash
        contract = Contract.objects.select_related("client", "booking", "photographer__user").filter(
            pk=delivery.lifecycle_context.get("contract_id"), review_token_revoked_at__isnull=True).first()
        if not contract or not contract.photographer.user.can_login or not contract.review_token_expires_at or contract.review_token_expires_at <= timezone.now():
            return False
        if contract.review_token_digest != delivery.lifecycle_context.get("digest"):
            return False
        if not contract.sent_to_email or contract.sent_to_email.casefold() != contract.client.email.casefold():
            return False
        if [email.casefold() for email in delivery.recipients] != [contract.sent_to_email.casefold()]:
            return False
        if contract.booking.photographer_id != contract.photographer_id or contract.booking.client_id != contract.client_id:
            return False
        digest = _content_hash(contract.rendered_content)
        if not ContractPhotographerSignature.objects.filter(contract=contract, content_hash=digest).exists():
            return False
        if delivery.lifecycle_kind == "contract.review":
            return contract.status in (Contract.Status.SENT, Contract.Status.VIEWED) and not ContractSignature.objects.filter(contract=contract).exists()
        return contract.status == Contract.Status.SIGNED and ContractSignature.objects.filter(contract=contract, content_hash=digest).exists()
    if delivery.lifecycle_kind == "account.password_reset":
        from django.contrib.auth import get_user_model
        from django.utils.crypto import constant_time_compare
        from apps.accounts.recovery import password_reset_state
        user = get_user_model().objects.filter(pk=delivery.lifecycle_context.get("user_id"), is_active=True).first()
        if not user or not user.has_usable_password():
            return False
        email = getattr(user, user.get_email_field_name(), "")
        return bool(email and [value.casefold() for value in delivery.recipients] == [email.casefold()]
            and constant_time_compare(password_reset_state(user), delivery.lifecycle_context.get("state", "")))
    if delivery.lifecycle_kind == "account.verify":
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.filter(pk=delivery.lifecycle_context.get("user_id"), is_active=True).first()
        if not user or user.email_verified:
            return False
        # Token is in the existing payload, never duplicated in lifecycle metadata.
        from django.utils.crypto import salted_hmac
        state = salted_hmac("email-lifecycle-account", str(user.pk) + "|" + user.email + "|" + str(user.password) + "|" + str(getattr(user, "email_verified_at", ""))).hexdigest()
        return state == delivery.lifecycle_context.get("state")
    return False


def stop_locked(delivery, status, reason):
    delivery.status = status
    delivery.last_error = reason
    delivery.next_attempt_at = None
    delivery.save(update_fields=["status", "last_error", "next_attempt_at"])


@transaction.atomic
def cancel_queued(*, delivery_id, event_key):
    """Caller must authorize the domain action and supply its exact event key."""
    delivery = EmailDelivery.objects.select_for_update().filter(pk=delivery_id, event_key=event_key).first()
    if not delivery or delivery.status not in QUEUED:
        return False
    stop_locked(delivery, EmailDelivery.Status.CANCELLED, "CancelledByDomain")
    return True


def check_before_claim(delivery, now):
    if delivery.expires_at and delivery.expires_at <= now:
        stop_locked(delivery, EmailDelivery.Status.EXPIRED, "ExpiredBeforeDispatch")
        return False
    from .models import EmailSupersession
    if delivery.supersession_scope and not EmailSupersession.objects.filter(scope=delivery.supersession_scope, current_id=delivery.pk).exists():
        stop_locked(delivery, EmailDelivery.Status.CANCELLED, 'Superseded')
        return False
    if delivery.payload_purged_at or not eligible(delivery):
        stop_locked(delivery, EmailDelivery.Status.CANCELLED, "NoLongerEligible")
        return False
    return True


def purge_sensitive_payloads(limit=200):
    """Keep correlation and audit metadata; erase terminal sensitive message bodies."""
    now = timezone.now()
    ids = list(EmailDelivery.objects.filter(models.Q(status__in=TERMINAL) | models.Q(status=EmailDelivery.Status.UNCERTAIN, expires_at__lte=now)), sensitive=True, payload_purged_at__isnull=True).order_by("pk").values_list("pk", flat=True)[:limit])
    return EmailDelivery.objects.filter(models.Q(status__in=TERMINAL) | models.Q(status=EmailDelivery.Status.UNCERTAIN, expires_at__lte=now), pk__in=ids, sensitive=True, payload_purged_at__isnull=True).update(encrypted_payload='', plain_body="", html_body="", subject="[redacted]", lifecycle_context={}, payload_purged_at=now)
