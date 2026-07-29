from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.db.models import Q
import hashlib
import secrets


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


private_gallery_storage = FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


def gallery_photo_path(instance, filename):
    """Keep originals in an owner/gallery namespace (served only by an authorized view)."""
    return f"galleries/{instance.photographer_id}/{instance.gallery_id}/{filename}"


class GalleryPhotoQuerySet(models.QuerySet):
    def for_photographer(self, photographer):
        return self.filter(photographer=photographer)


class GalleryPhoto(models.Model):
    """Storage-agnostic upload record for a gallery original."""

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        UPLOADING = "uploading", "Uploading"
        PAUSED = "paused", "Paused"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    gallery = models.ForeignKey(Gallery, on_delete=models.CASCADE, related_name="photos")
    photographer = models.ForeignKey("accounts.PhotographerProfile", on_delete=models.CASCADE, related_name="gallery_photos")
    file = models.ImageField(storage=private_gallery_storage, upload_to=gallery_photo_path, validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])])
    original_name = models.CharField(max_length=255)
    file_size = models.PositiveBigIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    is_cover = models.BooleanField(default=False)
    is_visible = models.BooleanField(default=True)
    error_message = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = GalleryPhotoQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["photographer", "status", "-created_at"], name="photo_owner_status_created")]

    def clean(self):
        if self.gallery_id and self.photographer_id and self.gallery.photographer_id != self.photographer_id:
            raise ValidationError({"gallery": "Gallery must belong to this photographer."})


class AlbumQuerySet(models.QuerySet):
    def for_photographer(self, photographer):
        return self.filter(gallery__photographer=photographer)


class Album(models.Model):
    """A curated, ordered collection of photos within a gallery."""

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Public"
        CLIENT_ONLY = "client_only", "Client Only"
        HIDDEN = "hidden", "Hidden"

    gallery = models.ForeignKey(Gallery, on_delete=models.CASCADE, related_name="albums")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.CLIENT_ONLY)
    cover_image = models.ImageField(upload_to="galleries/albums/covers/%Y/%m/", blank=True)
    cover_photo = models.ForeignKey(GalleryPhoto, on_delete=models.SET_NULL, related_name="cover_for_albums", blank=True, null=True)
    display_order = models.PositiveIntegerField(default=0)
    photos = models.ManyToManyField(GalleryPhoto, through="AlbumPhoto", related_name="albums", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AlbumQuerySet.as_manager()

    class Meta:
        ordering = ["display_order", "-updated_at"]
        constraints = [models.UniqueConstraint(fields=["gallery", "name"], name="album_gallery_name_unique")]
        indexes = [models.Index(fields=["gallery", "visibility", "display_order"], name="album_gallery_visibility_order")]

    def clean(self):
        if self.cover_photo_id and self.gallery_id and self.cover_photo.gallery_id != self.gallery_id:
            raise ValidationError({"cover_photo": "Cover photo must belong to this album's gallery."})

    def __str__(self):
        return self.name


class AlbumPhoto(models.Model):
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name="album_photos")
    photo = models.ForeignKey(GalleryPhoto, on_delete=models.CASCADE, related_name="album_memberships")
    position = models.PositiveIntegerField(default=0)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "added_at"]
        constraints = [models.UniqueConstraint(fields=["album", "photo"], name="album_photo_unique")]
        indexes = [models.Index(fields=["album", "position"], name="album_photo_position")]

    def clean(self):
        if self.album_id and self.photo_id and self.album.gallery_id != self.photo.gallery_id:
            raise ValidationError({"photo": "Photo and album must belong to the same gallery."})


class GalleryPermission(models.Model):
    """The gallery-wide client access policy, kept separate from presentation data."""

    class Watermark(models.TextChoices):
        NONE = "none", "None"
        PREVIEW = "preview", "Preview Only"
        ALL = "all", "All Images"

    gallery = models.OneToOneField(Gallery, on_delete=models.CASCADE, related_name="permissions")
    view_gallery = models.BooleanField(default=True)
    download_images = models.BooleanField(default=True)
    download_originals = models.BooleanField(default=False)
    favorite_photos = models.BooleanField(default=True)
    comment = models.BooleanField(default=False)
    share_gallery = models.BooleanField(default=True)
    purchase_prints = models.BooleanField(default=False)
    automatic_gallery_lock = models.BooleanField(default=False)
    download_expires_at = models.DateTimeField(blank=True, null=True)
    watermark = models.CharField(max_length=12, choices=Watermark.choices, default=Watermark.PREVIEW)
    updated_at = models.DateTimeField(auto_now=True)


class GallerySettings(models.Model):
    """Presentation, download, preference, and discovery settings for a gallery."""

    class WatermarkPosition(models.TextChoices):
        CENTER = "center", "Center"
        TOP_LEFT = "top_left", "Top left"
        TOP_RIGHT = "top_right", "Top right"
        BOTTOM_LEFT = "bottom_left", "Bottom left"
        BOTTOM_RIGHT = "bottom_right", "Bottom right"

    class Theme(models.TextChoices):
        LIGHT = "light", "Light"
        DARK = "dark", "Dark"
        EDITORIAL = "editorial", "Editorial"

    gallery = models.OneToOneField(Gallery, on_delete=models.CASCADE, related_name="settings")
    studio_logo = models.ImageField(upload_to="galleries/branding/%Y/%m/", blank=True)
    accent_color = models.CharField(max_length=7, default="#B42328")
    watermark_position = models.CharField(max_length=20, choices=WatermarkPosition.choices, default=WatermarkPosition.BOTTOM_RIGHT)
    theme = models.CharField(max_length=20, choices=Theme.choices, default=Theme.LIGHT)
    allow_downloads = models.BooleanField(default=True)
    allow_original_downloads = models.BooleanField(default=False)
    zip_downloads = models.BooleanField(default=True)
    download_limit = models.PositiveIntegerField(blank=True, null=True)
    enable_favorites = models.BooleanField(default=True)
    enable_comments = models.BooleanField(default=False)
    enable_slideshow = models.BooleanField(default=True)
    show_exif_data = models.BooleanField(default=False)
    show_file_names = models.BooleanField(default=False)
    gallery_url = models.SlugField(max_length=220)
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class GalleryInvitation(models.Model):
    """An email-address invitation; delivery can be attached by a future mail service."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        DISABLED = "disabled", "Disabled"

    gallery = models.ForeignKey(Gallery, on_delete=models.CASCADE, related_name="invitations")
    client_name = models.CharField(max_length=160)
    email = models.EmailField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    invited_at = models.DateTimeField(auto_now_add=True)
    last_access_at = models.DateTimeField(blank=True, null=True)
    resent_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-invited_at"]
        constraints = [models.UniqueConstraint(fields=["gallery", "email"], name="gallery_invitation_email_unique")]


class AccessToken(models.Model):
    """Revocable access credential. Only a SHA-256 digest is persisted."""

    invitation = models.ForeignKey(GalleryInvitation, on_delete=models.CASCADE, related_name="access_tokens")
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    expires_at = models.DateTimeField(blank=True, null=True)
    last_used_at = models.DateTimeField(blank=True, null=True)
    revoked_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def issue(cls, invitation, *, expires_at=None):
        """Create a cryptographically secure token and return it once with its record."""
        raw_token = secrets.token_urlsafe(32)
        record = cls.objects.create(
            invitation=invitation,
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            expires_at=expires_at,
        )
        return record, raw_token

    @classmethod
    def digest(cls, raw_token):
        return hashlib.sha256(raw_token.encode()).hexdigest()
