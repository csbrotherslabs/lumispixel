"""Growth records that complement, rather than duplicate, CRM and booking data."""
from django.db import models

from apps.clients.models import PhotographerOwnedModel


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
    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="review_requests")
    sent_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class ReferralLink(PhotographerOwnedModel):
    class ReferralType(models.TextChoices):
        CLIENT = "client", "Client"
        VENDOR = "vendor", "Vendor"
        PHOTOGRAPHER = "photographer", "Photographer"
        PARTNER = "partner", "Partner"
        TEAM_MEMBER = "team_member", "Team member"

    label = models.CharField(max_length=150)
    code = models.SlugField(max_length=80)
    referral_type = models.CharField(max_length=20, choices=ReferralType.choices)
    referrer_name = models.CharField(max_length=150)
    visits = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["photographer", "code"], name="unique_referral_code_per_owner")]


class ReferralAttribution(PhotographerOwnedModel):
    """Connects an existing lead/booking to its referral link without copying either record."""

    referral_link = models.ForeignKey(ReferralLink, on_delete=models.CASCADE, related_name="attributions")
    lead = models.OneToOneField("clients.Lead", on_delete=models.CASCADE, related_name="referral_attribution")
    booking = models.OneToOneField("clients.ClientSession", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="referral_attribution")
    created_at = models.DateTimeField(auto_now_add=True)
