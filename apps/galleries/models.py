from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class GalleryQuerySet(models.QuerySet):
    def for_photographer(self, photographer):
        return self.filter(photographer=photographer)


class Gallery(models.Model):
    """A photographer-owned collection prepared for client delivery."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        UPLOADING = "uploading", "Uploading"
        PROCESSING = "processing", "Processing"
        REVIEW = "review", "Review"
        READY = "ready", "Ready"
        PUBLISHED = "published", "Published"
        DELIVERED = "delivered", "Delivered"
        ARCHIVED = "archived", "Archived"
        EXPIRED = "expired", "Expired"

    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        PASSWORD = "password", "Password protected"
        PUBLIC = "public", "Public"

    photographer = models.ForeignKey(
        "accounts.PhotographerProfile", on_delete=models.CASCADE, related_name="galleries"
    )
    client = models.ForeignKey(
        "clients.Client", on_delete=models.SET_NULL, related_name="galleries", blank=True, null=True
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)
    description = models.TextField(blank=True)
    event_date = models.DateField(blank=True, null=True)
    cover_image = models.ImageField(upload_to="galleries/covers/%Y/%m/", blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.PRIVATE)
    image_count = models.PositiveIntegerField(default=0)
    favorite_count = models.PositiveIntegerField(default=0)
    download_count = models.PositiveIntegerField(default=0)
    storage_used = models.PositiveBigIntegerField(default=0, help_text="Storage used in bytes.")
    published_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = GalleryQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["photographer", "slug"], name="gallery_owner_slug_unique"),
            models.CheckConstraint(
                condition=Q(expires_at__isnull=True) | Q(published_at__isnull=True) | Q(expires_at__gt=models.F("published_at")),
                name="gallery_expiry_after_publish",
            ),
        ]
        indexes = [
            models.Index(fields=["photographer", "status", "-created_at"], name="gallery_owner_status_created"),
        ]

    def clean(self):
        if self.client_id and self.photographer_id and self.client.photographer_id != self.photographer_id:
            raise ValidationError({"client": "Choose a client belonging to this photographer."})

    def __str__(self):
        return self.name
