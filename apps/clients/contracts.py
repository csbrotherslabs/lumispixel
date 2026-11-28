"""Canonical, tenant-safe operations for booking contracts and merge fields."""
import hashlib
import re
import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from apps.notifications.email_delivery import public_url, queue_transactional_email
from django.core.validators import validate_email
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import formats, timezone

from .models import (Contract, ContractEvent, ContractPhotographerSignature,
                     ContractSignature, ContractTemplate, ClientSession, ClientActivity)
from .payment_terms import payment_clause, validate_saved_payment_terms
from .contract_pdfs import build_signed_snapshot, generate_signed_contract_pdf


MERGE_FIELDS = {
    "client.first_name": "Client first name",
    "client.last_name": "Client last name",
    "client.full_name": "Client full name",
    "client.email": "Client email",
    "booking.service": "Booking service/title",
    "booking.date": "Booking date",
    "booking.start_time": "Booking start time",
    "booking.location": "Booking location",
    "booking.value": "Agreed booking value",
    "booking.payment_terms": "Agreed payment schedule",
    "booking.currency": "Currency",
    "booking.deposit_amount": "Down payment",
    "booking.deposit_due_date": "Down payment due date",
    "booking.balance_due": "Remaining balance",
    "booking.balance_due_date": "Balance due date",
    "workspace.name": "Workspace/business name",
    "photographer.name": "Photographer/studio name",
}
MERGE_PATTERN = re.compile(r"{{\s*([a-z][a-z0-9_.]*)\s*}}")
REVIEW_LINK_LIFETIME = timedelta(days=30)
SENDABLE_STATUSES = (Contract.Status.DRAFT, Contract.Status.READY, Contract.Status.SENT, Contract.Status.VIEWED)
DEFAULT_SIGNATURE_CONSENT = (
    "I have reviewed and agree to the terms of this contract and intend this electronic "
    "signature to be legally binding."
)


class ContractSignatureForm(forms.Form):
    signer_name = forms.CharField(label="Signer full name", max_length=200, strip=True)
    signature_value = forms.CharField(required=False, widget=forms.HiddenInput)
    consent_accepted = forms.BooleanField(label="Agreement", required=True)

    def clean_signer_name(self):
        value = self.cleaned_data["signer_name"]
        if not value:
            raise forms.ValidationError("Enter your full name.")
        return value

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data["signature_value"] = cleaned_data.get("signer_name", "")
        return cleaned_data


class PhotographerSignatureForm(ContractSignatureForm):
    signer_name = forms.CharField(label="Your full legal name", max_length=200, strip=True)


class ContractDeliveryError(Exception):
    """A client review email could not be delivered."""


def unknown_merge_fields(content):
    """Return unsupported tokens without interpreting template content."""
    return sorted({field for field in MERGE_PATTERN.findall(content or "") if field not in MERGE_FIELDS})


def merge_context(booking):
    """Build values exclusively from the contract booking's persisted tenant data."""
    local_start = timezone.localtime(booking.starts_at)
    studio = booking.photographer
    owner = studio.user
    studio_name = studio.business_name or studio.display_name or owner.full_name or owner.email
    total = Decimal(str(booking.booking_value))
    deposit = Decimal(str(booking.deposit_amount))
    return {
        "client.first_name": booking.client.first_name,
        "client.last_name": booking.client.last_name,
        "client.full_name": str(booking.client),
        "client.email": booking.client.email,
        "booking.service": booking.session_type,
        "booking.date": formats.date_format(local_start, "DATE_FORMAT"),
        "booking.start_time": formats.time_format(local_start, "TIME_FORMAT"),
        "booking.location": booking.location,
        "booking.value": (f"{booking.payment_currency} {total:,.2f}" if booking.pricing_confirmed else "Not yet agreed"),
        "booking.payment_terms": payment_clause(booking),
        "booking.currency": booking.payment_currency,
        "booking.deposit_amount": str(booking.deposit_amount),
        "booking.deposit_due_date": str(booking.deposit_due_date or ""),
        "booking.balance_due": str(total - deposit),
        "booking.balance_due_date": str(booking.balance_due_date or ""),
        "workspace.name": studio_name,
        "photographer.name": studio_name,
    }


def render_merge_fields(content, booking):
    """Resolve known fields; retain unknown tokens visibly and harmlessly."""
    values = merge_context(booking)
    return MERGE_PATTERN.sub(lambda match: str(values.get(match.group(1), match.group(0))), content or "")


def contract_preview_content(contract, content=None):
    """Render the contract snapshot with current persisted merge values."""
    if content is None and contract.locked_at and contract.rendered_content:
        return contract.rendered_content
    source = contract.content if content is None else content
    # Upgrade the exact legacy starter paragraph, without rewriting custom legal terms.
    legacy = "Service fee: {{ booking.value }}. The parties will confirm the deposit, payment schedule and applicable taxes in writing before signing."
    source = (source or "").replace(legacy, "{{ booking.payment_terms }}")
    source = re.sub(r"(?m)^Service fee: [^\n]*?\. The parties will confirm the deposit, payment schedule and applicable taxes in writing before signing\.", "{{ booking.payment_terms }}", source)
    source = source.replace("The parties will confirm the service fee, deposit, payment schedule and applicable taxes in writing before signing.", "{{ booking.payment_terms }}")
    has_payment_clause = any(match.group(1) == "booking.payment_terms" for match in MERGE_PATTERN.finditer(source))
    body = render_merge_fields(source, contract.booking)
    if not has_payment_clause:
        body += "\n\nAgreed payment terms\n" + payment_clause(contract.booking)
    if contract.booking.pricing_confirmed:
        body += "\n\nThe agreed payment terms generated from the booking govern the service fee, down payment and payment deadlines and supersede any inconsistent amounts or payment dates elsewhere in this agreement."
    return body


def validate_contract_for_email(contract):
    errors = []
    if not contract.client_id:
        errors.append("Add a client before sending this contract.")
    email = (contract.client.email if contract.client_id else "").strip()
    try:
        validate_email(email)
    except ValidationError:
        errors.append("Add a valid client email address before sending.")
    if not (contract.content or "").strip():
        errors.append("Add contract content before sending.")
    if contract.status not in SENDABLE_STATUSES:
        errors.append("This contract is not in a sendable status.")
    if contract.booking_id and contract.booking.photographer_id != contract.photographer_id:
        errors.append("This contract does not belong to the active workspace.")
    if not contract.photographer.user.can_login:
        errors.append("This workspace is not active.")
    if errors:
        raise ValidationError(errors)
    return email


def _token_digest(raw_token):
    return hashlib.sha256(raw_token.encode()).hexdigest()


@transaction.atomic
def send_contract_for_review(*, contract, actor, build_absolute_uri):
    """Deliver a rotating opaque review link, then atomically record success."""
    contract = Contract.objects.select_for_update().select_related(
        "client", "booking", "photographer", "photographer__user"
    ).get(pk=contract.pk, photographer=contract.photographer)
    if not ContractPhotographerSignature.objects.filter(contract=contract).exists():
        raise ValidationError("The photographer must sign before sending.")
    recipient = validate_contract_for_email(contract)
    signature = ContractPhotographerSignature.objects.get(contract=contract)
    if not contract.locked_at or not contract.rendered_content or signature.content_hash != _content_hash(contract.rendered_content):
        raise ValidationError("The signed document does not match the recorded signature. Prepare a replacement agreement.")
    raw_token = secrets.token_urlsafe(32)
    review_url = public_url(reverse("clients:contract-review", kwargs={"token": raw_token}))
    rendered_content = contract_preview_content(contract)
    context = {"contract": contract, "review_url": review_url, "studio": contract.photographer}
    now = timezone.now()
    digest = _token_digest(raw_token)
    # Preserve one previously usable link across repeated replacements, only for the same recipient.
    if contract.sent_to_email.casefold() != recipient.casefold() or contract.review_token_revoked_at:
        contract.previous_review_digest = ""
        contract.previous_review_expires_at = None
    elif not contract.previous_review_expires_at or contract.previous_review_expires_at <= now:
        contract.previous_review_digest = contract.review_token_digest
        contract.previous_review_expires_at = contract.review_token_expires_at
    try:
        delivery = queue_transactional_email(
            event_key=f"contract.review:{contract.pk}:{digest}",
            subject=f"Review your contract: {contract.title}",
            plain_body=render_to_string("clients/contracts/email/review.txt", context),
            html_body=render_to_string("clients/contracts/email/review.html", context),
            recipients=[recipient], sensitive=True, expires_at=now + REVIEW_LINK_LIFETIME,
            lifecycle_kind="contract.review", lifecycle_context={"contract_id": contract.pk, "digest": digest},
            supersession_scope=f"contract.review:{contract.pk}",
        )
        if not delivery:
            raise ValueError("Missing recipient")
    except Exception as exc:
        raise ContractDeliveryError("Contract email could not be queued.") from exc

    was_sent = contract.send_count > 0
    contract.rendered_content = rendered_content
    contract.review_token_digest = _token_digest(raw_token)
    contract.review_token_expires_at = now + REVIEW_LINK_LIFETIME
    contract.review_token_revoked_at = None
    contract.sent_to_email = recipient
    contract.send_count += 1
    contract.last_sent_at = now
    contract.sent_at = contract.sent_at or now
    contract.locked_at = contract.locked_at or now
    if contract.status in (Contract.Status.DRAFT, Contract.Status.READY):
        contract.status = Contract.Status.SENT
    contract.save(update_fields=(
        "rendered_content", "review_token_digest", "review_token_expires_at", "review_token_revoked_at",
        "sent_to_email", "send_count", "last_sent_at", "sent_at", "locked_at", "status", "updated_at",
        "previous_review_digest", "previous_review_expires_at",
    ))
    ContractEvent.objects.create(
        contract=contract, actor=actor,
        event_type=ContractEvent.EventType.RESENT if was_sent else ContractEvent.EventType.SENT,
        metadata={"recipient": recipient, "contract_version": contract.version, "send_number": contract.send_count, "delivery_id": delivery.pk, "delivery_state": "queued"},
    )
    return contract


def _valid_review_token(contract, raw_token):
    if not contract or contract.review_token_revoked_at or not contract.photographer.user.can_login:
        return False
    if not contract.sent_to_email or contract.sent_to_email.casefold() != contract.client.email.casefold():
        return False
    digest = _token_digest(raw_token)
    expiry = contract.review_token_expires_at if digest == contract.review_token_digest else (
        contract.previous_review_expires_at if digest == contract.previous_review_digest else None)
    return bool(expiry and expiry > timezone.now())


@transaction.atomic
def open_contract_review(raw_token):
    """Resolve one unexpired token and record only its first successful view."""
    if not raw_token:
        return None
    contract = Contract.objects.select_for_update().select_related(
        "client", "booking", "photographer", "photographer__user"
    ).filter(Q(review_token_digest=_token_digest(raw_token)) | Q(previous_review_digest=_token_digest(raw_token)), review_token_revoked_at__isnull=True).first()
    if not _valid_review_token(contract, raw_token):
        return None
    if contract.status == Contract.Status.SIGNED:
        return contract
    if contract.status not in (Contract.Status.SENT, Contract.Status.VIEWED):
        return None
    if contract.viewed_at is None:
        now = timezone.now()
        contract.viewed_at = now
        contract.status = Contract.Status.VIEWED
        contract.save(update_fields=("viewed_at", "status", "updated_at"))
        ContractEvent.objects.create(
            contract=contract, event_type=ContractEvent.EventType.VIEWED,
            metadata={"recipient": contract.sent_to_email, "contract_version": contract.version},
        )
    return contract


def _content_hash(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@transaction.atomic
def sign_contract_as_photographer(*, contract, actor, signer_name, signature_value,
                                  consent_accepted, ip_address=None, user_agent="", expected_content_hash=None):
    """Countersign and lock the exact workspace-side contract snapshot."""
    contract = Contract.objects.select_for_update().select_related(
        "booking", "client", "photographer"
    ).get(pk=contract.pk, photographer=contract.photographer)
    if ContractPhotographerSignature.objects.filter(contract=contract).exists():
        raise ValidationError("This contract has already been signed by the photographer.")
    if contract.status not in (Contract.Status.DRAFT, Contract.Status.READY):
        raise ValidationError("Sign the contract before sending it to the client.")
    signer_name = (signer_name or "").strip()
    signature_value = (signature_value or "").strip()
    if not signer_name:
        raise ValidationError({"signer_name": "Enter your full name."})
    if not signature_value:
        raise ValidationError({"signature_value": "Type your signature."})
    if consent_accepted is not True:
        raise ValidationError({"consent_accepted": "You must agree before signing."})
    validate_saved_payment_terms(contract.booking)
    now = timezone.now()
    rendered_content = contract_preview_content(contract)
    digest = _content_hash(rendered_content)
    if expected_content_hash is not None and expected_content_hash != digest:
        raise ValidationError("The agreement changed since you opened it. Review the updated document before signing.")
    consent_text = getattr(settings, "CONTRACT_SIGNATURE_CONSENT_TEXT", DEFAULT_SIGNATURE_CONSENT)
    signature = ContractPhotographerSignature.objects.create(
        contract=contract, signer_name=signer_name, signature_value=signature_value,
        consent_accepted=True, consent_text=consent_text, signed_at=now,
        content_hash=digest, contract_version=contract.version,
        photographer=contract.photographer, signed_by=actor, ip_address=ip_address,
        user_agent=(user_agent or "")[:512],
    )
    contract.rendered_content = rendered_content
    contract.locked_at = contract.locked_at or now
    contract.status = Contract.Status.READY
    contract.save(update_fields=("rendered_content", "locked_at", "status", "updated_at"))
    ContractEvent.objects.create(
        contract=contract, actor=actor, event_type=ContractEvent.EventType.PHOTOGRAPHER_SIGNED,
        metadata={"signer": signer_name, "signed_at": now.isoformat(),
                  "content_hash": digest, "contract_version": contract.version},
    )
    return signature


def sign_contract(*, raw_token, signer_name, signature_value, consent_accepted, ip_address=None, user_agent=""):
    """Atomically accept the exact delivered snapshot addressed by an opaque token."""
    if not raw_token:
        raise ValidationError("This contract review link is invalid.")
    with transaction.atomic():
        contract = Contract.objects.select_for_update(of=("self",)).select_related(
            "client", "booking", "photographer", "photographer__user", "photographer_signature"
        ).filter(Q(review_token_digest=_token_digest(raw_token)) | Q(previous_review_digest=_token_digest(raw_token)), review_token_revoked_at__isnull=True).first()
        now = timezone.now()
        if not _valid_review_token(contract, raw_token):
            raise ValidationError("This contract review link is invalid or has expired.")
        if contract.status == Contract.Status.SIGNED or ContractSignature.objects.filter(contract=contract).exists():
            raise ValidationError("This contract has already been signed.")
        if contract.status not in (Contract.Status.SENT, Contract.Status.VIEWED):
            raise ValidationError("This contract is not available for signing.")
        signer_name = (signer_name or "").strip()
        signature_value = (signature_value or "").strip()
        if not signer_name:
            raise ValidationError({"signer_name": "Enter your full name."})
        if not signature_value:
            raise ValidationError({"signature_value": "Type your signature."})
        if consent_accepted is not True:
            raise ValidationError({"consent_accepted": "You must agree before signing."})
        consent_text = getattr(settings, "CONTRACT_SIGNATURE_CONSENT_TEXT", DEFAULT_SIGNATURE_CONSENT)
        digest = _content_hash(contract.rendered_content)
        if not ContractPhotographerSignature.objects.filter(
            contract=contract, photographer_id=contract.photographer_id,
            content_hash=digest, contract_version=contract.version, consent_accepted=True,
        ).exists():
            raise ValidationError("The photographer signature does not match this agreement.")
        if contract.booking.photographer_id != contract.photographer_id or contract.booking.client_id != contract.client_id:
            raise ValidationError("The agreement does not match its booking.")
        signature = ContractSignature(
            contract=contract, signer_name=signer_name, signature_value=signature_value,
            signature_type=ContractSignature.SignatureType.TYPED, consent_accepted=True,
            consent_text=consent_text, signed_at=now, content_hash=digest,
            contract_version=contract.version, client=contract.client, photographer=contract.photographer,
            ip_address=ip_address, user_agent=(user_agent or "")[:512],
        )
        signature.signed_snapshot = build_signed_snapshot(contract, signature)
        signature.save()
        # Explicit signature, not a GET or mail scanner, retires alternate signing links.
        if _token_digest(raw_token) == contract.previous_review_digest:
            contract.review_token_digest = contract.previous_review_digest
            contract.review_token_expires_at = contract.previous_review_expires_at
        contract.previous_review_digest = ""
        contract.previous_review_expires_at = None
        contract.signed_at = now
        contract.locked_at = contract.locked_at or now
        contract.status = Contract.Status.SIGNED
        contract.save(update_fields=("signed_at", "locked_at", "status", "updated_at", "review_token_digest", "review_token_expires_at", "previous_review_digest", "previous_review_expires_at"))
        ContractEvent.objects.create(
            contract=contract, event_type=ContractEvent.EventType.SIGNED,
            metadata={"contract_id": contract.pk, "contract_version": contract.version,
                      "signer": signer_name, "signed_at": now.isoformat(), "content_hash": digest,
                      "client_id": contract.client_id, "workspace_id": contract.photographer_id},
        )
        # Confirm only active tentative reservations with both signatures.
        # A conditional update prevents resurrecting cancelled/completed bookings.
        if ContractPhotographerSignature.objects.filter(contract=contract, content_hash=digest).exists():
            from apps.marketplace.models import PlatformBooking
            unacknowledged = PlatformBooking.objects.filter(session_id=contract.booking_id, acknowledged_at__isnull=True).exists()
            updated = 0 if unacknowledged else ClientSession.objects.filter(
                pk=contract.booking_id, photographer_id=contract.photographer_id,
                client_id=contract.client_id, status=ClientSession.Status.TENTATIVE,
                event_kind=ClientSession.EventKind.BOOKING,
            ).update(status=ClientSession.Status.CONFIRMED, confirmed_at=now, updated_at=now)
            if updated:
                ClientActivity.objects.create(
                    photographer_id=contract.photographer_id, client_id=contract.client_id,
                    booking_id=contract.booking_id, event_type=ClientActivity.EventType.BOOKING_UPDATED,
                    description="Booking automatically confirmed after both parties signed the agreement.",
                    metadata={"contract_id": contract.pk, "before": "tentative", "after": "confirmed"},
                )
        from apps.notifications.intents import require_email
        require_email(event_key=f"contract.signed:{contract.pk}:{contract.review_token_digest}",
            recipients=[contract.sent_to_email], kind="contract.signed")
    generate_signed_contract_pdf(contract.pk)
    return signature


@transaction.atomic
def send_signed_contract_copy_link(*, contract, signed_pdf_url):
    contract = Contract.objects.select_for_update().select_related("client", "photographer__user").get(pk=contract.pk)
    if contract.status != Contract.Status.SIGNED or contract.review_token_revoked_at:
        raise ValidationError("Signed agreement unavailable.")
    if not contract.review_token_expires_at or contract.review_token_expires_at <= timezone.now():
        raise ValidationError("Signed agreement link expired.")
    if contract.sent_to_email.casefold() != contract.client.email.casefold():
        raise ValidationError("Contract recipient changed.")
    from urllib.parse import urlsplit
    from django.urls import resolve
    match = resolve(urlsplit(signed_pdf_url).path)
    token = match.kwargs.get("token", "")
    if not token or _token_digest(token) != contract.review_token_digest:
        raise ValidationError("Invalid signed agreement link.")
    context = {"contract": contract, "signed_pdf_url": public_url(reverse("clients:signed-contract-pdf-download", args=[token])), "studio": contract.photographer}
    return queue_transactional_email(
        event_key=f"contract.signed:{contract.pk}:{contract.review_token_digest}",
        subject=f"Your signed contract: {contract.title}",
        plain_body=render_to_string("clients/contracts/email/signed.txt", context),
        html_body=render_to_string("clients/contracts/email/signed.html", context),
        recipients=[contract.sent_to_email], sensitive=True, expires_at=contract.review_token_expires_at,
        lifecycle_kind="contract.signed", lifecycle_context={"contract_id": contract.pk, "digest": contract.review_token_digest},
    )


@transaction.atomic
def create_contract_from_template(*, booking, template, actor):
    """Create one draft snapshot, safely coalescing duplicate form submissions."""
    if booking.photographer_id != template.photographer_id:
        raise ValidationError({"template": "The template and booking must belong to the same photographer."})
    # Serialize creation for this booking so a browser retry/double-click cannot
    # create two indistinguishable active drafts. A new contract remains possible
    # after the existing agreement has left draft state.
    type(booking).objects.select_for_update().get(pk=booking.pk)
    existing = Contract.objects.filter(
        photographer=booking.photographer, booking=booking, client=booking.client,
        template=template, version=template.version, status=Contract.Status.DRAFT,
    ).first()
    if existing:
        return existing
    contract = Contract(
        photographer=booking.photographer,
        booking=booking,
        client=booking.client,
        template=template,
        title=template.title,
        content=template.content,
        version=template.version,
        status=Contract.Status.DRAFT,
        created_by=actor,
    )
    contract.full_clean()
    contract.save()
    ContractEvent.objects.create(
        contract=contract,
        actor=actor,
        event_type=ContractEvent.EventType.CREATED,
        metadata={"template_id": template.pk, "template_version": template.version},
    )
    return contract
