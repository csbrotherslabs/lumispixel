"""Lifecycle checks for queued email; never claim recall of an external submission."""
from decimal import Decimal, InvalidOperation
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
    if delivery.lifecycle_kind == "booking.notice":
        from apps.clients.models import ClientSession
        from apps.marketplace.models import PlatformBooking
        context = delivery.lifecycle_context
        booking = PlatformBooking.objects.select_related("session__client", "photographer__user").filter(
            session_id=context.get("session_id"), photographer_id=context.get("studio_id")).first()
        if not booking or not booking.photographer.user.can_login:
            return False
        session = booking.session
        if session.photographer_id != booking.photographer_id or session.client.photographer_id != booking.photographer_id:
            return False
        expected = {"confirmed": ClientSession.Status.CONFIRMED, "awaiting": ClientSession.Status.TENTATIVE}.get(context.get("event"))
        if not expected or session.status != expected or not booking.acknowledged_at:
            return False
        audience = context.get("audience")
        if audience not in ("photographer", "client"):
            return False
        email = booking.photographer.user.email if audience == "photographer" else session.client.email
        return bool(email and [r.casefold() for r in delivery.recipients] == [email.casefold()])
    if delivery.lifecycle_kind in ("privacy.notice", "privacy.review"):
        from apps.visual_search.models import ClientBiometricDeletionRequest, BiometricDeletionDiscoveryCandidate
        from apps.galleries.models import Gallery
        from django.contrib.auth import get_user_model
        context = delivery.lifecycle_context
        item = ClientBiometricDeletionRequest.objects.select_related("user").filter(pk=context.get("request_id")).first()
        if not item:
            return False
        if delivery.lifecycle_kind == "privacy.notice":
            event = context.get("event")
            if event not in ("requested", "completed", "unverified"):
                return False
            if (event == "completed") != (item.status == ClientBiometricDeletionRequest.Status.COMPLETED):
                return False
            email = item.user.email
        else:
            if item.status == ClientBiometricDeletionRequest.Status.COMPLETED:
                return False
            owner = get_user_model().objects.filter(pk=context.get("owner_id"), is_active=True).first()
            if not owner:
                return False
            linked = Gallery.objects.filter(photographer__user=owner, client__user_id=item.user_id).exists()
            candidate = BiometricDeletionDiscoveryCandidate.objects.filter(request=item, gallery__photographer__user=owner, status__in=["pending", "unverified"]).exists()
            if not (linked or candidate):
                return False
            email = owner.email
        return bool(email and [r.casefold() for r in delivery.recipients] == [email.casefold()])
    if delivery.lifecycle_kind == "booking.acknowledgment":
        from apps.marketplace.models import PlatformBooking
        from apps.clients.models import ClientSession
        context = delivery.lifecycle_context
        booking = PlatformBooking.objects.select_related("session__client", "photographer__user").filter(
            pk=context.get("booking_id"), photographer_id=context.get("studio_id"),
            acknowledged_at__isnull=True, customer__isnull=True,
            verification_expires_at__gt=timezone.now(), verification_digest=context.get("digest")).first()
        return bool(booking and booking.photographer.user.can_login
            and booking.session.status == ClientSession.Status.TENTATIVE
            and booking.session.photographer_id == booking.photographer_id
            and booking.session.client.photographer_id == booking.photographer_id
            and not booking.session.client.user_id
            and booking.session.client.email.casefold() == booking.client_email.casefold()
            and [r.casefold() for r in delivery.recipients] == [booking.client_email.casefold()])
    if delivery.lifecycle_kind == "payment.receipt":
        from apps.clients.models import InvoicePayment
        context = delivery.lifecycle_context
        payment = InvoicePayment.objects.select_related("invoice__client", "photographer__user").filter(
            pk=context.get("payment_id"), photographer_id=context.get("studio_id"), status="completed").first()
        return bool(payment and payment.photographer.user.can_login
            and payment.invoice.photographer_id == payment.photographer_id
            and payment.invoice.client.photographer_id == payment.photographer_id
            and [r.casefold() for r in delivery.recipients] == [payment.invoice.client.email.casefold()])
    if delivery.lifecycle_kind == "booking.balance":
        from apps.clients.models import ClientSession
        from apps.dashboard.financial_automation import reminder_eligible, outstanding_booking
        context = delivery.lifecycle_context
        booking = ClientSession.objects.select_related("photographer__user", "client").filter(
            pk=context.get("booking_id"), photographer_id=context.get("studio_id")).first()
        return bool(booking and context.get("day") == timezone.localdate().isoformat()
            and reminder_eligible(booking, timezone.localdate())
            and booking.starts_at.isoformat() == context.get("starts_at")
            and booking.payment_currency == context.get("currency")
            and str(outstanding_booking(booking)) == context.get("balance")
            and [r.casefold() for r in delivery.recipients] == [booking.photographer.user.email.casefold()])
    if delivery.lifecycle_kind == "invoice.email":
        from apps.clients.models import ClientInvoice
        context = delivery.lifecycle_context
        invoice = ClientInvoice.objects.select_related("client", "photographer__user").filter(
            pk=context.get("invoice_id"), photographer_id=context.get("studio_id")).first()
        try:
            expected_paid = Decimal(context["amount_paid"])
            expected_total = Decimal(context["total"])
        except (KeyError, TypeError, ValueError, InvalidOperation):
            return False
        return bool(invoice and invoice.photographer.user.can_login
            and invoice.client.photographer_id == invoice.photographer_id
            and invoice.status in (ClientInvoice.Status.SENT, ClientInvoice.Status.PARTIALLY_PAID)
            and invoice.amount_paid < invoice.total
            and (context.get("purpose") != "reminder" or invoice.reminders_enabled)
            and invoice.amount_paid == expected_paid
            and invoice.total == expected_total
            and invoice.currency == context.get("currency")
            and (invoice.due_date.isoformat() if invoice.due_date else None) == context.get("due_date")
            and [email.casefold() for email in delivery.recipients] == [invoice.client.email.casefold()])
    if delivery.lifecycle_kind == "gallery.expiry":
        from apps.galleries.models import GalleryInvitation, Gallery, GalleryPermission
        from apps.workflows.models import AutomationExecution
        context = delivery.lifecycle_context
        invitation = GalleryInvitation.objects.select_related("gallery__photographer__user").filter(
            pk=context.get("invitation_id"), gallery_id=context.get("gallery_id"),
            gallery__photographer_id=context.get("studio_id"),
            status__in=(GalleryInvitation.Status.PENDING, GalleryInvitation.Status.ACTIVE)).first()
        if not invitation:
            return False
        gallery = invitation.gallery
        return bool(gallery.photographer.user.can_login and not gallery.deleted_at and not gallery.archived_at
            and gallery.status in (Gallery.Status.PUBLISHED, Gallery.Status.DELIVERED)
            and gallery.expires_at and gallery.expires_at > timezone.now()
            and gallery.expires_at.isoformat() == context.get("expires_at")
            and not GalleryPermission.objects.filter(gallery=gallery, view_gallery=False).exists()
            and AutomationExecution.objects.filter(pk=context.get("execution_id"), photographer_id=gallery.photographer_id, rule__enabled=True).exists()
            and [email.casefold() for email in delivery.recipients] == [invitation.email.casefold()])
    if delivery.lifecycle_kind == "studio.invite":
        from apps.dashboard.models import StudioMembership
        from apps.dashboard.team_invitations import INVITABLE_ROLES
        context = delivery.lifecycle_context
        membership = StudioMembership.objects.select_related("studio__user").filter(
            pk=context.get("membership_id"), studio_id=context.get("studio_id"),
            status=StudioMembership.Status.INVITED, role__in=INVITABLE_ROLES).first()
        return bool(membership and membership.studio.user.can_login
            and membership.role == context.get("role")
            and membership.invitation_token_digest == context.get("digest")
            and membership.invitation_expires_at and membership.invitation_expires_at > timezone.now()
            and [email.casefold() for email in delivery.recipients] == [membership.invitation_email.casefold()])
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
    if delivery.lifecycle_kind == "employee.invite":
        from apps.internal_ops.models import EmployeeProfile
        from apps.accounts.recovery import password_reset_state
        from django.utils.crypto import constant_time_compare
        context = delivery.lifecycle_context
        employee = EmployeeProfile.objects.select_related("user").filter(
            pk=context.get("employee_id"), user_id=context.get("user_id")).first()
        if not employee or not employee.can_access_internal or not employee.user.is_active:
            return False
        user = employee.user
        return (
            [email.casefold() for email in delivery.recipients] == [user.email.casefold()]
            and context.get("setup") == (not user.has_usable_password())
            and constant_time_compare(password_reset_state(user), context.get("state", ""))
            and context.get("title") == employee.title
            and context.get("role_id") == employee.role_id
            and context.get("department_id") == employee.department_id
        )
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
    ids = list(
        EmailDelivery.objects.filter(
            models.Q(status__in=TERMINAL)
            | models.Q(status=EmailDelivery.Status.UNCERTAIN, expires_at__lte=now),
            sensitive=True,
            payload_purged_at__isnull=True,
        ).order_by("pk").values_list("pk", flat=True)[:limit]
    )
    return EmailDelivery.objects.filter(models.Q(status__in=TERMINAL) | models.Q(status=EmailDelivery.Status.UNCERTAIN, expires_at__lte=now), pk__in=ids, sensitive=True, payload_purged_at__isnull=True).update(encrypted_payload='', plain_body="", html_body="", subject="[redacted]", lifecycle_context={}, payload_purged_at=now)
