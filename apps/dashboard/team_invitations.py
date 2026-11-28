"""Secure, studio-scoped invitation creation, delivery, and token validation."""
import hashlib
import secrets
from datetime import timedelta
from smtplib import SMTPException

from django import forms
from django.conf import settings
from django.db import transaction
from apps.notifications.email_delivery import public_url, queue_transactional_email
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User, phone_validator
from apps.dashboard.models import StudioInvitationEvent, StudioMembership
from apps.dashboard.access import ROLE_SUMMARIES

INVITATION_LIFETIME = timedelta(days=7)
INVITATION_RESEND_COOLDOWN = timedelta(minutes=1)
INVITABLE_ROLES = (StudioMembership.Role.MANAGER, StudioMembership.Role.PHOTOGRAPHER)


class InvitationForm(forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField(max_length=254)
    role = forms.ChoiceField(choices=[(role, StudioMembership.Role(role).label) for role in INVITABLE_ROLES])
    primary_location = forms.CharField(max_length=150)
    phone = forms.CharField(max_length=30, required=False, validators=[phone_validator])
    specialties = forms.CharField(max_length=500, required=False)
    message = forms.CharField(max_length=1000, required=False, widget=forms.Textarea)

    def __init__(self, *args, studio=None, **kwargs):
        self.studio = studio
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"].strip()).lower()
        if StudioMembership.objects.filter(studio=self.studio, status=StudioMembership.Status.ACTIVE).filter(
                Q(user__email__iexact=email) | Q(invitation_email__iexact=email)).exists():
            raise forms.ValidationError("This person is already an active member of your studio.")
        if StudioMembership.objects.filter(studio=self.studio, status=StudioMembership.Status.INVITED,
                                           invitation_email__iexact=email).exists():
            raise forms.ValidationError("A pending invitation already exists. Use Resend or Revoke below.")
        return email


def _digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def prepare_token():
    """Return an unsaved invitation credential and its validity window."""
    token = secrets.token_urlsafe(32)
    now = timezone.now()
    return token, _digest(token), now, now + INVITATION_LIFETIME


def apply_token(membership, token_digest, sent_at, expires_at):
    from apps.notifications.models import EmailDelivery
    current_sent = bool(membership.pk and membership.invitation_token_digest) and EmailDelivery.objects.filter(
        lifecycle_kind="studio.invite", lifecycle_context__membership_id=membership.pk,
        lifecycle_context__digest=membership.invitation_token_digest,
        status=EmailDelivery.Status.SENT,
    ).exists()
    if current_sent or not membership.previous_invitation_expires_at or membership.previous_invitation_expires_at <= sent_at:
        membership.previous_invitation_digest = membership.invitation_token_digest
        membership.previous_invitation_expires_at = membership.invitation_expires_at
    membership.invitation_token_digest = token_digest
    membership.invitation_sent_at = sent_at
    membership.invitation_expires_at = expires_at
    membership.status = StudioMembership.Status.INVITED
    membership.save(update_fields=["invitation_token_digest", "invitation_sent_at", "invitation_expires_at", "status", "updated_at", "previous_invitation_digest", "previous_invitation_expires_at"])


def issue_token(membership):
    token, digest, sent_at, expires_at = prepare_token()
    apply_token(membership, digest, sent_at, expires_at)
    return token


def send_invitation(request, membership, token):
    try:
        path = reverse("photographer_workspace:invitation_accept", kwargs={"token": token})
        context = {"membership": membership, "studio": membership.studio,
                   "role_summary": ROLE_SUMMARIES[membership.role],
                   "invitation_url": public_url(path), "brand_name": "LumisPixel"}
        delivery = queue_transactional_email(
            event_key=f"studio.invite:{membership.pk}:{_digest(token)}",
            subject=f"You're invited to join {membership.studio.display_name or 'a studio'} on LumisPixel",
            plain_body=render_to_string("photographer_workspace/team/email/invitation.txt", context),
            html_body=render_to_string("photographer_workspace/team/email/invitation.html", context),
            recipients=[membership.invitation_email], sensitive=True,
            expires_at=membership.invitation_expires_at, lifecycle_kind="studio.invite",
            lifecycle_context={"membership_id": membership.pk, "studio_id": membership.studio_id,
                "digest": _digest(token), "role": membership.role},
            supersession_scope=f"studio.invite:{membership.pk}",
        )
        if not delivery:
            raise ValueError("Missing recipient")
        return delivery
    except Exception as exc:
        raise RuntimeError("Invitation could not be queued") from exc


def find_valid_invitation(token, *, lock=False):
    queryset = StudioMembership.objects.select_related("studio", "studio__user", "invited_by")
    if lock:
        # Lock only StudioMembership. invited_by is nullable, so an unrestricted
        # FOR UPDATE across select_related() produces a PostgreSQL outer-join
        # locking error. Django/PostgreSQL's OF clause preserves eager loading
        # while protecting the invitation row that acceptance mutates.
        queryset = queryset.select_for_update(of=("self",))
    digest = _digest(token)
    now = timezone.now()
    return queryset.filter(status=StudioMembership.Status.INVITED, role__in=INVITABLE_ROLES).filter(
        Q(invitation_token_digest=digest, invitation_expires_at__gt=now) |
        Q(previous_invitation_digest=digest, previous_invitation_expires_at__gt=now)
    ).first()


def record(membership, actor, action):
    StudioInvitationEvent.objects.create(membership=membership, actor=actor, action=action)
