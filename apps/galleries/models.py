from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
import hashlib
import secrets

from .storage import get_private_gallery_storage


class GalleryQuerySet(models.QuerySet):
    def active(self):
        """Galleries that belong in day-to-day workspace lists."""
        return self.filter(archived_at__isnull=True, deleted_at__isnull=True).exclude(status=Gallery.Status.ARCHIVED)

    def archived(self):
        return self.filter(archived_at__isnull=False, deleted_at__isnull=True)

    def for_photographer(self, photographer):
        return self.filter(photographer=photographer)


class Gallery(models.Model):
    assigned_members = models.ManyToManyField("dashboard.StudioMembership", blank=True, related_name="assigned_galleries")
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

    class ArchiveReason(models.TextChoices):
        COMPLETED = "completed", "Project Completed"
        EXPIRED = "expired", "Gallery Expired"
        CLIENT_REQUESTED = "client_requested", "Client Requested"
        STORAGE = "storage", "Storage Management"
        DUPLICATE = "duplicate", "Duplicate Gallery"
        OTHER = "other", "Other"

    class RetentionType(models.TextChoices):
        INDEFINITE = "indefinite", "Retained Indefinitely"
        UNTIL_DATE = "until_date", "Retained Until Date"
        SCHEDULED = "scheduled", "Scheduled for Deletion"
        DELETION_PENDING = "deletion_pending", "Deletion Pending"

    photographer = models.ForeignKey("accounts.PhotographerProfile", on_delete=models.CASCADE, related_name="galleries")
    client = models.ForeignKey("clients.Client", on_delete=models.SET_NULL, related_name="galleries", blank=True, null=True)
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
    archived_at = models.DateTimeField(blank=True, null=True)
    archived_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="archived_galleries")
    archive_reason = models.CharField(max_length=24, choices=ArchiveReason.choices, blank=True)
    previous_status = models.CharField(max_length=20, choices=Status.choices, blank=True)
    retention_type = models.CharField(max_length=24, choices=RetentionType.choices, default=RetentionType.INDEFINITE)
    retention_until = models.DateField(blank=True, null=True)
    scheduled_deletion_at = models.DateTimeField(blank=True, null=True)
    deleted_at = models.DateTimeField(blank=True, null=True, help_text="Soft-deletion marker used before permanent removal.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = GalleryQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["photographer", "slug"], name="gallery_owner_slug_unique"),
            models.CheckConstraint(condition=Q(expires_at__isnull=True) | Q(published_at__isnull=True) | Q(expires_at__gt=models.F("published_at")), name="gallery_expiry_after_publish"),
        ]
        indexes = [models.Index(fields=["photographer", "status", "-created_at"], name="gallery_owner_status_created")]

    def clean(self):
        if self.client_id and self.photographer_id and self.client.photographer_id != self.photographer_id:
            raise ValidationError({"client": "Choose a client belonging to this photographer."})

    def __str__(self):
        return self.name


class GalleryArchivePolicy(models.Model):
    photographer = models.OneToOneField("accounts.PhotographerProfile", on_delete=models.CASCADE, related_name="gallery_archive_policy")
    archive_delivered = models.BooleanField(default=False)
    archive_after_expiration = models.BooleanField(default=True)
    inactivity_days = models.PositiveIntegerField(blank=True, null=True)
    default_retention_days = models.PositiveIntegerField(default=365)
    warn_before_deletion = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)


class GalleryActivityQuerySet(models.QuerySet):
    def for_photographer(self, photographer):
        return self.filter(photographer=photographer)


class GalleryActivity(models.Model):
    class ActorType(models.TextChoices):
        PHOTOGRAPHER = "photographer", "Photographer"
        CLIENT = "client", "Client"
        SYSTEM = "system", "System"

    class EventType(models.TextChoices):
        GALLERY_CREATED = "gallery_created", "Gallery created"
        GALLERY_UPDATED = "gallery_updated", "Gallery updated"
        GALLERY_PUBLISHED = "gallery_published", "Gallery published"
        GALLERY_ARCHIVED = "gallery_archived", "Gallery archived"
        PHOTOS_UPLOADED = "photos_uploaded", "Photos uploaded"
        PHOTOS_DELETED = "photos_deleted", "Photos deleted"
        ALBUM_CREATED = "album_created", "Album created"
        ALBUM_UPDATED = "album_updated", "Album updated"
        AI_STARTED = "ai_started", "AI processing started"
        AI_COMPLETED = "ai_completed", "AI processing completed"
        CLIENT_INVITED = "client_invited", "Client invited"
        CLIENT_VIEWED = "client_viewed", "Client viewed gallery"
        CLIENT_FAVORITED = "client_favorited", "Client favorited a photo"
        CLIENT_COMMENTED = "client_commented", "Client commented"
        PHOTO_DOWNLOADED = "photo_downloaded", "Photo downloaded"
        GALLERY_DOWNLOADED = "gallery_downloaded", "Gallery downloaded"
        GALLERY_SHARED = "gallery_shared", "Gallery shared"
        STORE_ORDER_CREATED = "store_order_created", "Store order created"
        PAYMENT_CHANGED = "payment_changed", "Payment status changed"
        PERMISSION_CHANGED = "permission_changed", "Permission changed"
        SETTINGS_CHANGED = "settings_changed", "Settings changed"

    photographer = models.ForeignKey("accounts.PhotographerProfile", on_delete=models.CASCADE, related_name="gallery_activity")
    gallery = models.ForeignKey(Gallery, on_delete=models.CASCADE, related_name="activity")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="gallery_activity", blank=True, null=True)
    actor_type = models.CharField(max_length=20, choices=ActorType.choices, default=ActorType.SYSTEM)
    event_type = models.CharField(max_length=40, choices=EventType.choices)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    related_object_type = models.CharField(max_length=40, blank=True)
    related_object_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = GalleryActivityQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["photographer", "gallery", "-created_at"], name="activity_owner_gallery_date"), models.Index(fields=["gallery", "event_type", "-created_at"], name="activity_gallery_type_date")]

    def clean(self):
        if self.gallery_id and self.photographer_id and self.gallery.photographer_id != self.photographer_id:
            raise ValidationError({"gallery": "Activity and gallery must have the same photographer."})


class GalleryAnalyticsEventQuerySet(models.QuerySet):
    def for_photographer(self, photographer):
        return self.filter(photographer=photographer)

    def for_gallery(self, gallery):
        return self.filter(gallery=gallery, photographer=gallery.photographer)


class GalleryAnalyticsEvent(models.Model):
    class EventType(models.TextChoices):
        VIEW = "view", "Gallery view"
        PHOTO_VIEW = "photo_view", "Photo view"
        DOWNLOAD = "download", "Photo download"
        GALLERY_DOWNLOAD = "gallery_download", "Full gallery download"
        FAVORITE = "favorite", "Favorite"
        COMMENT = "comment", "Comment"
        SHARE = "share", "Share"
        PURCHASE = "purchase", "Purchase"

    class Device(models.TextChoices):
        DESKTOP = "desktop", "Desktop"
        MOBILE = "mobile", "Mobile"
        TABLET = "tablet", "Tablet"
        UNKNOWN = "unknown", "Unknown"

    photographer = models.ForeignKey("accounts.PhotographerProfile", on_delete=models.CASCADE, related_name="gallery_analytics_events")
    gallery = models.ForeignKey(Gallery, on_delete=models.CASCADE, related_name="analytics_events")
    visitor_identifier = models.CharField(max_length=64, blank=True, help_text="Opaque, application-generated identifier only.")
    authenticated_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="gallery_analytics_events")
    session_identifier = models.CharField(max_length=64, blank=True)
    event_type = models.CharField(max_length=24, choices=EventType.choices)
    related_photo = models.ForeignKey("GalleryPhoto", on_delete=models.SET_NULL, blank=True, null=True, related_name="analytics_events")
    related_album = models.ForeignKey("Album", on_delete=models.SET_NULL, blank=True, null=True, related_name="analytics_events")
    device_category = models.CharField(max_length=12, choices=Device.choices, default=Device.UNKNOWN)
    source = models.CharField(max_length=24, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    objects = GalleryAnalyticsEventQuerySet.as_manager()

    class Meta:
        ordering = ["-occurred_at", "-pk"]
        indexes = [models.Index(fields=["photographer", "gallery", "-occurred_at"], name="analytics_owner_gallery_date"), models.Index(fields=["gallery", "event_type", "-occurred_at"], name="analytics_gallery_type_date"), models.Index(fields=["gallery", "visitor_identifier", "-occurred_at"], name="analytics_gallery_visitor")]

    def clean(self):
        if self.gallery_id and self.photographer_id and self.gallery.photographer_id != self.photographer_id:
            raise ValidationError({"gallery": "Analytics event and gallery must have the same photographer."})
        if self.related_photo_id and self.related_photo.gallery_id != self.gallery_id:
            raise ValidationError({"related_photo": "Photo must belong to this gallery."})
        if self.related_album_id and self.related_album.gallery_id != self.gallery_id:
            raise ValidationError({"related_album": "Album must belong to this gallery."})


private_gallery_storage = get_private_gallery_storage()


def gallery_photo_path(instance, filename):
    return f"galleries/{instance.photographer_id}/{instance.gallery_id}/{filename}"


class GalleryPhotoQuerySet(models.QuerySet):
    def for_photographer(self, photographer):
        return self.filter(photographer=photographer)


class GalleryPhoto(models.Model):
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


class GalleryStore(models.Model):
    gallery = models.OneToOneField(Gallery, on_delete=models.CASCADE, related_name="store")
    photographer = models.ForeignKey("accounts.PhotographerProfile", on_delete=models.CASCADE, related_name="gallery_stores")
    enabled = models.BooleanField(default=False)
    name = models.CharField(max_length=160, blank=True)
    message = models.TextField(blank=True)
    currency = models.CharField(max_length=3, default="USD")
    collect_sales_tax = models.BooleanField(default=False)
    expires_at = models.DateTimeField(blank=True, null=True)
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    digital_delivery_enabled = models.BooleanField(default=True)
    delivery_message = models.CharField(max_length=300, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.gallery_id and self.photographer_id and self.gallery.photographer_id != self.photographer_id:
            raise ValidationError({"gallery": "Store and gallery must have the same photographer."})


class StoreProduct(models.Model):
    class ProductType(models.TextChoices):
        DIGITAL = "digital_download", "Digital Download"
        GALLERY = "full_gallery_download", "Full Gallery Download"
        PRINT = "print", "Print"
        CANVAS = "canvas", "Canvas"

    store = models.ForeignKey(GalleryStore, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    product_type = models.CharField(max_length=32, choices=ProductType.choices)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    active = models.BooleanField(default=True)
    fulfillment_sku = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class GalleryOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FULFILLING = "fulfilling", "Fulfilling"
        FULFILLED = "fulfilled", "Fulfilled"
        REFUNDED = "refunded", "Refunded"
        CANCELLED = "cancelled", "Cancelled"

    gallery = models.ForeignKey(Gallery, on_delete=models.CASCADE, related_name="orders")
    store = models.ForeignKey(GalleryStore, on_delete=models.CASCADE, related_name="orders")
    photographer = models.ForeignKey("accounts.PhotographerProfile", on_delete=models.CASCADE, related_name="gallery_orders")
    client = models.ForeignKey("clients.Client", on_delete=models.SET_NULL, blank=True, null=True, related_name="gallery_orders")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    currency = models.CharField(max_length=3, default="USD")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_reference = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.gallery_id and self.photographer_id and self.gallery.photographer_id != self.photographer_id:
            raise ValidationError({"gallery": "Order and gallery must have the same photographer."})
        if self.store_id and self.gallery_id and self.store.gallery_id != self.gallery_id:
            raise ValidationError({"store": "Store must belong to this gallery."})


class GalleryOrderItem(models.Model):
    order = models.ForeignKey(GalleryOrder, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(StoreProduct, on_delete=models.PROTECT, related_name="order_items")
    photo = models.ForeignKey(GalleryPhoto, on_delete=models.SET_NULL, blank=True, null=True, related_name="order_items")
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    def clean(self):
        if self.photo_id and self.photo.gallery_id != self.order.gallery_id:
            raise ValidationError({"photo": "Photo must belong to the order's gallery."})


class GalleryAccess(models.Model):
    class AccessType(models.TextChoices):
        EMAIL = "email", "Email invitation"
        LINK = "link", "Private link"
        PASSWORD = "password", "Password"
        PUBLIC = "public", "Public"

    gallery = models.ForeignKey(Gallery, on_delete=models.CASCADE, related_name="access_records")
    client = models.ForeignKey("clients.Client", on_delete=models.SET_NULL, blank=True, null=True, related_name="gallery_access")
    email = models.EmailField(blank=True)
    access_type = models.CharField(max_length=20, choices=AccessType.choices, default=AccessType.LINK)
    token_hash = models.CharField(max_length=64, blank=True, db_index=True)
    password_hash = models.CharField(max_length=255, blank=True)
    can_download = models.BooleanField(default=True)
    can_favorite = models.BooleanField(default=True)
    can_comment = models.BooleanField(default=False)
    expires_at = models.DateTimeField(blank=True, null=True)
    revoked_at = models.DateTimeField(blank=True, null=True)
    first_viewed_at = models.DateTimeField(blank=True, null=True)
    last_viewed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["gallery", "email", "revoked_at"], name="access_gallery_email_revoked")]

    @classmethod
    def issue_token(cls):
        raw = secrets.token_urlsafe(32)
        return raw, hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def token_matches(self, raw_token):
        if not raw_token:
            return False
        return secrets.compare_digest(self.token_hash, hashlib.sha256(raw_token.encode("utf-8")).hexdigest())
