import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from .managers import UserManager

phone_validator = RegexValidator(
    regex=r"^\+?[0-9().\-\s]{7,20}$",
    message="Enter a valid phone number using digits, spaces, parentheses, hyphens, and an optional leading +.",
)


class User(AbstractBaseUser, PermissionsMixin):
    class PrimaryRole(models.TextChoices):
        CLIENT = "client", "Client"
        PHOTOGRAPHER = "photographer", "Photographer"

    class Workspace(models.TextChoices):
        CLIENT = "client", "Client"
        PHOTOGRAPHER = "photographer", "Photographer"
        MARKETPLACE = "marketplace", "Marketplace"
        OPERATIONS = "operations", "Operations"

    class AccountStatus(models.TextChoices):
        PENDING_EMAIL_VERIFICATION = "pending_email_verification", "Pending email verification"
        ACTIVE = "active", "Active"
        RESTRICTED = "restricted", "Restricted"
        SUSPENDED = "suspended", "Suspended"
        DEACTIVATED = "deactivated", "Deactivated"
        SCHEDULED_FOR_DELETION = "scheduled_for_deletion", "Scheduled for deletion"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    primary_role = models.CharField(max_length=20, choices=PrimaryRole.choices, default=PrimaryRole.CLIENT)
    last_active_workspace = models.CharField(max_length=20, choices=Workspace.choices, default=Workspace.CLIENT)
    account_status = models.CharField(
        max_length=40,
        choices=AccountStatus.choices,
        default=AccountStatus.PENDING_EMAIL_VERIFICATION,
    )
    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(blank=True, null=True)
    onboarding_completed = models.BooleanField(default=False)
    required_password_reset = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(blank=True, null=True)
    privacy_policy_accepted_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        constraints = [models.UniqueConstraint(models.functions.Lower("email"), name="accounts_user_email_lower_unique")]
        ordering = ["email"]

    @property
    def username(self):
        return self.email

    def get_username(self):
        return self.email

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if self.email:
            self.email = User.objects.normalize_email(self.email)
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def display_name(self):
        return self.full_name or self.email

    @property
    def is_client(self):
        return self.primary_role == self.PrimaryRole.CLIENT

    @property
    def is_photographer(self):
        return self.primary_role == self.PrimaryRole.PHOTOGRAPHER

    @property
    def has_client_profile(self):
        return hasattr(self, "client_profile")

    @property
    def has_photographer_profile(self):
        return hasattr(self, "photographer_profile")

    @property
    def is_account_active(self):
        return self.is_active and self.account_status in {
            self.AccountStatus.ACTIVE,
            self.AccountStatus.PENDING_EMAIL_VERIFICATION,
            self.AccountStatus.RESTRICTED,
        }

    @property
    def can_login(self):
        return self.is_account_active and self.account_status not in {
            self.AccountStatus.SUSPENDED,
            self.AccountStatus.DEACTIVATED,
            self.AccountStatus.SCHEDULED_FOR_DELETION,
        }

    @property
    def can_use_marketplace_as_client(self):
        return self.can_login and self.has_client_profile

    @property
    def can_use_photographer_workspace(self):
        return self.can_login and self.has_photographer_profile

    def mark_email_verified(self, commit=True):
        self.email_verified = True
        self.email_verified_at = timezone.now()
        if self.account_status == self.AccountStatus.PENDING_EMAIL_VERIFICATION:
            self.account_status = self.AccountStatus.ACTIVE
        if commit:
            self.save(update_fields=["email_verified", "email_verified_at", "account_status", "updated_at"])


class ClientProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="client_profile")
    display_name = models.CharField(max_length=150, blank=True)
    profile_photo = models.ImageField(upload_to="client-profiles/", blank=True, null=True)
    country = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    timezone = models.CharField(max_length=64, blank=True)
    marketing_emails = models.BooleanField(default=False)
    onboarding_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name or f"Client profile for {self.user.display_name}"


class PhotographerProfile(models.Model):
    class BusinessType(models.TextChoices):
        INDIVIDUAL = "individual", "Individual"
        STUDIO = "studio", "Studio"

    class WebsiteTheme(models.TextChoices):
        ELEGANT = "elegant", "Elegant"
        MODERN = "modern", "Modern"
        SPORTS = "sports", "Sports"

    class VerificationStatus(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under review"
        ADDITIONAL_INFORMATION_REQUIRED = "additional_information_required", "Additional information required"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        SUSPENDED = "suspended", "Suspended"
        EXPIRED = "expired", "Expired"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="photographer_profile")
    display_name = models.CharField(max_length=150, blank=True)
    business_name = models.CharField(max_length=150, blank=True)
    slug = models.SlugField(max_length=180, unique=True)
    profile_photo = models.ImageField(upload_to="photographer_profiles/photos/", blank=True, null=True)
    business_logo = models.ImageField(upload_to="photographer_profiles/logos/", blank=True, null=True)
    phone_number = models.CharField(max_length=32, blank=True, validators=[phone_validator])
    website = models.URLField(blank=True)
    country = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    timezone = models.CharField(max_length=64, blank=True)
    business_type = models.CharField(max_length=20, choices=BusinessType.choices, default=BusinessType.INDIVIDUAL)
    years_of_experience = models.PositiveSmallIntegerField(blank=True, null=True)
    service_area = models.CharField(max_length=255, blank=True)
    willing_to_travel = models.BooleanField(default=False)
    default_currency = models.CharField(max_length=3, default="USD")
    instagram_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)
    tiktok_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    website_theme = models.CharField(max_length=20, choices=WebsiteTheme.choices, default=WebsiteTheme.ELEGANT)
    specialties = models.ManyToManyField("PhotographerSpecialty", related_name="photographer_profiles", blank=True)
    biography = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to="photographer-covers/", blank=True, null=True)
    accepts_marketplace_requests = models.BooleanField(default=False)
    verification_status = models.CharField(max_length=45, choices=VerificationStatus.choices, default=VerificationStatus.NOT_STARTED)
    verification_submitted_at = models.DateTimeField(blank=True, null=True)
    verified_at = models.DateTimeField(blank=True, null=True)
    verification_expires_at = models.DateTimeField(blank=True, null=True)
    onboarding_step = models.CharField(max_length=80, blank=True)
    onboarding_completed = models.BooleanField(default=False)
    payout_setup_completed = models.BooleanField(default=False)
    public_profile_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_name", "business_name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.display_name or self.business_name or self.user.display_name) or "photographer"
            slug = base
            counter = 2
            while PhotographerProfile.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name or self.business_name or self.user.display_name

    @property
    def is_verified(self):
        if self.verification_status != self.VerificationStatus.APPROVED:
            return False
        return not self.verification_expires_at or self.verification_expires_at > timezone.now()

    @property
    def can_publish_marketplace_listing(self):
        return self.is_verified and self.public_profile_enabled and self.accepts_marketplace_requests

    @property
    def can_receive_payouts(self):
        return self.is_verified and self.payout_setup_completed


class PhotographerSpecialty(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "photographer specialties"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
