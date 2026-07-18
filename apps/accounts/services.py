from dataclasses import dataclass
from smtplib import SMTPException

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.core import mail
from django.conf import settings

from .models import ClientProfile, PhotographerProfile
from config import settings

SIGNUP_INTENTS = {"find_photos", "marketplace", "general"}
PHOTOGRAPHER_FIRST_ONBOARDING_STEP = "business_information"

User = get_user_model()


class DuplicateEmailError(Exception):
    pass


class EmailDeliveryError(Exception):
    """Raised when a verification email cannot be handed off to the email backend."""


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.password}{user.email_verified}{user.email_verified_at}{timestamp}"


email_verification_token = EmailVerificationTokenGenerator()


def normalize_signup_intent(intent):
    return intent if intent in SIGNUP_INTENTS else "general"


@dataclass(frozen=True)
class SignupPayload:
    first_name: str
    last_name: str
    email: str
    password: str


def _create_base_user(payload, role):
    return User.objects.create_user(
        email=payload.email,
        password=payload.password,
        first_name=payload.first_name,
        last_name=payload.last_name,
        primary_role=role,
        last_active_workspace=User.Workspace.PHOTOGRAPHER if role == User.PrimaryRole.PHOTOGRAPHER else User.Workspace.CLIENT,
        account_status=User.AccountStatus.PENDING_EMAIL_VERIFICATION,
        email_verified=False,
        onboarding_completed=False,
        terms_accepted_at=timezone.now(),
        privacy_policy_accepted_at=timezone.now(),
    )


def create_client_account(payload):
    try:
        with transaction.atomic():
            if User.objects.filter(email__iexact=payload.email).exists():
                raise DuplicateEmailError
            user = _create_base_user(payload, User.PrimaryRole.CLIENT)
            ClientProfile.objects.get_or_create(user=user)
            return user
    except IntegrityError as exc:
        raise DuplicateEmailError from exc


def create_photographer_account(payload):
    try:
        with transaction.atomic():
            if User.objects.filter(email__iexact=payload.email).exists():
                raise DuplicateEmailError
            user = _create_base_user(payload, User.PrimaryRole.PHOTOGRAPHER)
            PhotographerProfile.objects.get_or_create(
                user=user,
                defaults={
                    "display_name": user.display_name,
                    "verification_status": PhotographerProfile.VerificationStatus.NOT_STARTED,
                    "onboarding_step": PHOTOGRAPHER_FIRST_ONBOARDING_STEP,
                },
            )
            return user
    except IntegrityError as exc:
        raise DuplicateEmailError from exc


def build_verification_url(request, user):
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    path = reverse("accounts:verify-email", kwargs={"uidb64": uidb64, "token": token})
    return request.build_absolute_uri(path)


def send_verification_email(request, user):

    email_connection = mail.get_connection(
        username=settings.EMAIL_HOST_USER,
        password=settings.EMAIL_HOST_PASSWORD,
        fail_silently=False,
    )
    email_connection.open()
    
    verification_url = build_verification_url(request, user)
    context = {
        "user": user, 
        "verification_url": verification_url, 
        "brand_name": "LumisPixel"
    }
    subject = "Verify your LumisPixel email address"
    text_body = render_to_string("accounts/email/verify_email.txt", context)
    html_body = render_to_string("accounts/email/verify_email.html", context)
    text_content = strip_tags(html_body)

    message = mail.EmailMultiAlternatives(subject, 
                                          text_content, 
                                          from_email=settings.EMAIL_HOST_USER,
                                          to=[user.email],
                                          connection = email_connection,)
    message.attach_alternative(html_body, "text/html")
    try:
        message.send()
        print("here")
    except (OSError, SMTPException) as exc:
        print("141")
        print(exc)
        raise EmailDeliveryError from exc
