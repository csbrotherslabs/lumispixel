"""Secure, studio-scoped invitation creation, delivery, and token validation."""
import hashlib
import secrets
from datetime import timedelta
from smtplib import SMTPException

from django import forms
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User, phone_validator
from apps.dashboard.models import StudioInvitationEvent, StudioMembership
from apps.dashboard.access import ROLE_SUMMARIES

INVITATION_LIFETIME = timedelta(days=7)
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


def issue_token(membership):
    token = secrets.token_urlsafe(32)
    membership.invitation_token_digest = _digest(token)
    membership.invitation_sent_at = timezone.now()
    membership.invitation_expires_at = timezone.now() + INVITATION_LIFETIME
    membership.status = StudioMembership.Status.INVITED
    membership.save(update_fields=["invitation_token_digest", "invitation_sent_at", "invitation_expires_at", "status", "updated_at"])
    return token


def send_invitation(request, membership, token):
    path = reverse("photographer_workspace:invitation_accept", kwargs={"token": token})
    context = {"membership": membership, "studio": membership.studio,
               "role_summary": ROLE_SUMMARIES[membership.role],
               "invitation_url": request.build_absolute_uri(path), "brand_name": "LumisPixel"}
    subject = f"You're invited to join {membership.studio.display_name or 'a studio'} on LumisPixel"
    text = render_to_string("photographer_workspace/team/email/invitation.txt", context)
    html = render_to_string("photographer_workspace/team/email/invitation.html", context)
    message = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL,
                                     [membership.invitation_email])
    message.attach_alternative(html, "text/html")
    try:
        message.send(fail_silently=False)
    except (OSError, SMTPException) as exc:
        raise RuntimeError("Invitation delivery failed") from exc


def find_valid_invitation(token, *, lock=False):
    queryset = StudioMembership.objects.select_related("studio", "studio__user", "invited_by")
    if lock:
        queryset = queryset.select_for_update()
    membership = queryset.filter(invitation_token_digest=_digest(token), status=StudioMembership.Status.INVITED).first()
    if not membership or not membership.invitation_expires_at or membership.invitation_expires_at <= timezone.now():
        if membership:
            membership.status = StudioMembership.Status.EXPIRED
            membership.invitation_token_digest = ""
            membership.save(update_fields=["status", "invitation_token_digest", "updated_at"])
        return None
    return membership


def record(membership, actor, action):
    StudioInvitationEvent.objects.create(membership=membership, actor=actor, action=action)
