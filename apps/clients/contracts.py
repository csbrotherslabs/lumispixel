"""Canonical, tenant-safe operations for booking contracts and merge fields."""
import hashlib
import re
import secrets
from datetime import timedelta

from django.conf import settings
from django import forms
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import formats, timezone

from .models import Contract, ContractEvent, ContractSignature, ContractTemplate


MERGE_FIELDS = {
    "client.first_name": "Client first name",
    "client.last_name": "Client last name",
    "client.full_name": "Client full name",
    "client.email": "Client email",
    "booking.service": "Booking service/title",
    "booking.date": "Booking date",
    "booking.start_time": "Booking start time",
    "booking.location": "Booking location",
    "booking.value": "Booking value",
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
    signature_value = forms.CharField(label="Type your signature", max_length=200, strip=True)
    consent_accepted = forms.BooleanField(label="Agreement", required=True)

    def clean_signer_name(self):
        value = self.cleaned_data["signer_name"]
        if not value:
            raise forms.ValidationError("Enter your full name.")
        return value

    def clean_signature_value(self):
        value = self.cleaned_data["signature_value"]
        if not value:
            raise forms.ValidationError("Type your signature.")
        return value


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
    return {
        "client.first_name": booking.client.first_name,
        "client.last_name": booking.client.last_name,
        "client.full_name": str(booking.client),
        "client.email": booking.client.email,
        "booking.service": booking.session_type,
        "booking.date": formats.date_format(local_start, "DATE_FORMAT"),
        "booking.start_time": formats.time_format(local_start, "TIME_FORMAT"),
        "booking.location": booking.location,
        "booking.value": formats.number_format(booking.booking_value, decimal_pos=2),
        "workspace.name": studio_name,
        "photographer.name": studio_name,
    }


def render_merge_fields(content, booking):
    """Resolve known fields; retain unknown tokens visibly and harmlessly."""
    values = merge_context(booking)
    return MERGE_PATTERN.sub(lambda match: str(values.get(match.group(1), match.group(0))), content or "")


def contract_preview_content(contract, content=None):
    """Render the contract snapshot with current persisted merge values."""
    return render_merge_fields(contract.content if content is None else content, contract.booking)


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
    recipient = validate_contract_for_email(contract)
    raw_token = secrets.token_urlsafe(32)
    review_url = build_absolute_uri(reverse("clients:contract-review", kwargs={"token": raw_token}))
    rendered_content = contract_preview_content(contract)
    context = {"contract": contract, "review_url": review_url, "studio": contract.photographer}
    message = EmailMultiAlternatives(
        f"Review your contract: {contract.title}",
        render_to_string("clients/contracts/email/review.txt", context),
        settings.DEFAULT_FROM_EMAIL,
        [recipient],
    )
    message.attach_alternative(render_to_string("clients/contracts/email/review.html", context), "text/html")
    try:
        delivered = message.send(fail_silently=False)
    except Exception as exc:
        raise ContractDeliveryError("Contract email delivery failed.") from exc
    if delivered != 1:
        raise ContractDeliveryError("Contract email delivery failed.")

    now = timezone.now()
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
    ))
    ContractEvent.objects.create(
        contract=contract, actor=actor,
        event_type=ContractEvent.EventType.RESENT if was_sent else ContractEvent.EventType.SENT,
        metadata={"recipient": recipient, "contract_version": contract.version, "send_number": contract.send_count},
    )
    return contract


@transaction.atomic
def open_contract_review(raw_token):
    """Resolve one unexpired token and record only its first successful view."""
    if not raw_token:
        return None
    contract = Contract.objects.select_for_update().select_related(
        "client", "booking", "photographer", "photographer__user"
    ).filter(review_token_digest=_token_digest(raw_token), review_token_revoked_at__isnull=True).first()
    if not contract or not contract.review_token_expires_at or contract.review_token_expires_at <= timezone.now():
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
def sign_contract(*, raw_token, signer_name, signature_value, consent_accepted, ip_address=None, user_agent=""):
    """Atomically accept the exact delivered snapshot addressed by an opaque token."""
    if not raw_token:
        raise ValidationError("This contract review link is invalid.")
    contract = Contract.objects.select_for_update().select_related(
        "client", "booking", "photographer"
    ).filter(review_token_digest=_token_digest(raw_token), review_token_revoked_at__isnull=True).first()
    now = timezone.now()
    if not contract or not contract.review_token_expires_at or contract.review_token_expires_at <= now:
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
    signature = ContractSignature.objects.create(
        contract=contract, signer_name=signer_name, signature_value=signature_value,
        signature_type=ContractSignature.SignatureType.TYPED, consent_accepted=True,
        consent_text=consent_text, signed_at=now, content_hash=digest,
        contract_version=contract.version, client=contract.client, photographer=contract.photographer,
        ip_address=ip_address, user_agent=(user_agent or "")[:512],
    )
    contract.signed_at = now
    contract.locked_at = contract.locked_at or now
    contract.status = Contract.Status.SIGNED
    contract.save(update_fields=("signed_at", "locked_at", "status", "updated_at"))
    ContractEvent.objects.create(
        contract=contract, event_type=ContractEvent.EventType.SIGNED,
        metadata={"contract_id": contract.pk, "contract_version": contract.version,
                  "signer": signer_name, "signed_at": now.isoformat(), "content_hash": digest,
                  "client_id": contract.client_id, "workspace_id": contract.photographer_id},
    )
    return signature


@transaction.atomic
def create_contract_from_template(*, booking, template, actor):
    """Create a draft snapshot without retaining live template content."""
    if booking.photographer_id != template.photographer_id:
        raise ValidationError({"template": "The template and booking must belong to the same photographer."})
    contract = Contract(
        photographer=booking.photographer,
        booking=booking,
        client=booking.client,
        template=template,
        title=template.title,
        content=render_merge_fields(template.content, booking),
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
