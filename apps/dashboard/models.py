"""Growth records that complement, rather than duplicate, CRM and booking data."""
from django.db import models
from django.utils import timezone

from apps.clients.models import PhotographerOwnedModel


class StudioMembership(models.Model):
    """A person's access and directory metadata within one photographer studio."""

    class Role(models.TextChoices):
        MANAGER = "studio_manager", "Studio Manager"
        PHOTOGRAPHER = "photographer", "Photographer"
        ASSISTANT = "assistant", "Assistant"
        EDITOR = "editor", "Editor"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INVITED = "invited", "Invited"
        EXPIRED = "invitation_expired", "Invitation expired"
        INACTIVE = "inactive", "Inactive"
        SUSPENDED = "access_suspended", "Access suspended"

    class Availability(models.TextChoices):
        AVAILABLE = "available", "Available"
        ASSIGNED = "assigned", "On assignment"
        LIMITED = "limited", "Limited"
        AWAY = "away", "Away"
        UNKNOWN = "not_configured", "Not configured"

    studio = models.ForeignKey("accounts.PhotographerProfile", on_delete=models.CASCADE,
                               related_name="memberships")
    user = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="studio_memberships")
    invitation_email = models.EmailField(blank=True)
    invitation_first_name = models.CharField(max_length=150, blank=True)
    invitation_last_name = models.CharField(max_length=150, blank=True)
    invitation_phone = models.CharField(max_length=30, blank=True)
    invitation_message = models.TextField(blank=True)
    invitation_token_digest = models.CharField(max_length=64, blank=True, editable=False)
    invited_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="studio_invitations_sent")
    invitation_sent_at = models.DateTimeField(null=True, blank=True)
    role = models.CharField(max_length=24, choices=Role.choices, default=Role.PHOTOGRAPHER)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.INVITED)
    primary_location = models.CharField(max_length=150, blank=True)
    specialties = models.ManyToManyField("accounts.PhotographerSpecialty", blank=True,
                                         related_name="studio_memberships")
    availability = models.CharField(max_length=24, choices=Availability.choices,
                                    default=Availability.UNKNOWN)
    current_assignment = models.CharField(max_length=180, blank=True)
    invitation_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["studio", "user"], condition=models.Q(user__isnull=False),
                                    name="unique_studio_user_membership"),
            models.UniqueConstraint(fields=["studio", "invitation_email"],
                                    condition=models.Q(status="invited"),
                                    name="unique_pending_studio_invitation_email"),
        ]

    @property
    def email(self):
        return self.user.email if self.user_id else self.invitation_email


class StudioInvitationEvent(models.Model):
    """Immutable audit entry for a studio invitation lifecycle action."""

    class Action(models.TextChoices):
        SENT = "sent", "Sent"
        RESENT = "resent", "Resent"
        REVOKED = "revoked", "Revoked"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"

    membership = models.ForeignKey(StudioMembership, on_delete=models.CASCADE,
                                   related_name="invitation_events")
    actor = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="studio_invitation_events")
    action = models.CharField(max_length=12, choices=Action.choices)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]


class Review(PhotographerOwnedModel):
    """A native LumisPixel review or a manually recorded external review."""

    class Source(models.TextChoices):
        LUMISPIXEL = "lumispixel", "LumisPixel"
        EXTERNAL = "external", "External (manual)"

    client = models.ForeignKey("clients.Client", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="growth_reviews")
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.LUMISPIXEL)
    source_name = models.CharField(max_length=80, blank=True)
    reviewer_name = models.CharField(max_length=150)
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    response = models.TextField(blank=True)
    reviewed_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-reviewed_at"]
        constraints = [models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5),
                                                name="growth_review_rating_1_5")]


class ReviewRequest(PhotographerOwnedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="review_requests")
    booking = models.ForeignKey("clients.ClientSession", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="review_requests")
    message = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SENT)
    requested_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-requested_at"]
        constraints = [models.UniqueConstraint(fields=["photographer", "booking"],
                                                condition=models.Q(booking__isnull=False),
                                                name="unique_review_request_per_booking")]


class ReferralLink(PhotographerOwnedModel):
    class ReferralType(models.TextChoices):
        CLIENT = "client", "Client"
        VENDOR = "vendor", "Vendor"
        PHOTOGRAPHER = "photographer", "Photographer"
        PARTNER = "partner", "Partner"
        TEAM_MEMBER = "team_member", "Team member"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        EXPIRED = "expired", "Expired"

    label = models.CharField(max_length=150)
    code = models.SlugField(max_length=80)
    referral_type = models.CharField(max_length=20, choices=ReferralType.choices)
    referrer_name = models.CharField(max_length=150)
    client = models.ForeignKey("clients.Client", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="referral_links")
    campaign = models.ForeignKey("dashboard.GrowthCampaign", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="referral_links")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    expires_at = models.DateTimeField(null=True, blank=True)
    visits = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["photographer", "code"], name="unique_referral_code_per_owner")]


class GrowthCampaign(PhotographerOwnedModel):
    """A lightweight campaign record; content authoring and publishing remain out of scope."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PLANNED = "planned", "Planned"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"

    name = models.CharField(max_length=150)
    campaign_type = models.CharField(max_length=80)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    target_audience = models.CharField(max_length=200, blank=True)
    channel = models.CharField(max_length=80, blank=True)
    tracking_link = models.URLField(blank=True)
    spend = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ReferralAttribution(PhotographerOwnedModel):
    """Connects an existing lead/booking to its referral link without copying either record."""

    referral_link = models.ForeignKey(ReferralLink, on_delete=models.CASCADE, related_name="attributions")
    lead = models.OneToOneField("clients.Lead", on_delete=models.CASCADE, related_name="referral_attribution")
    booking = models.OneToOneField("clients.ClientSession", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="referral_attribution")
    created_at = models.DateTimeField(auto_now_add=True)
