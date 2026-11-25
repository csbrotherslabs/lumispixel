from django.conf import settings
from django.db import models
from django.db.models import Q


class PlatformBooking(models.Model):
    """Provenance created only by the authenticated public booking endpoint."""
    session = models.OneToOneField("clients.ClientSession", on_delete=models.PROTECT, related_name="platform_booking")
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    photographer = models.ForeignKey("accounts.PhotographerProfile", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)


class BookingReview(models.Model):
    booking = models.OneToOneField(PlatformBooking, on_delete=models.CASCADE, related_name="review")
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(max_length=3000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        constraints = [models.CheckConstraint(condition=Q(rating__gte=1, rating__lte=5), name="marketplace_review_rating_range")]
