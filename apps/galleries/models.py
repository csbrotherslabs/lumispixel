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


class GalleryActivityQuerySet(models.QuerySet):
    def for_photographer(self, photographer):
        return self.filter(photographer=photographer)


class GalleryActivity(models.Model):
    """An immutable, photographer-owned audit entry for a gallery workflow."""

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
        indexes = [
            models.Index(fields=["photographer", "gallery", "-created_at"], name="activity_owner_gallery_date"),
            models.Index(fields=["gallery", "event_type", "-created_at"], name="activity_gallery_type_date"),
        ]

    def clean(self):
        if self.gallery_id and self.photographer_id and self.gallery.photographer_id != self.photographer_id:
            raise ValidationError({"gallery": "Activity and gallery must have the same photographer."})


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


class GalleryStore(models.Model):
    """Gallery-scoped storefront configuration; payment providers live outside this model."""
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
        FRAMED = "framed_print", "Framed Print"
        ALBUM = "photo_album", "Photo Album"
    class Fulfillment(models.TextChoices):
        DIGITAL = "digital", "Digital delivery"
        PHYSICAL = "physical", "Physical fulfillment"
    class Resolution(models.TextChoices):
        WEB = "web", "Web size"
        HIGH = "high", "High resolution"
        ORIGINAL = "original", "Original"
    store = models.ForeignKey(GalleryStore, on_delete=models.CASCADE, related_name="products")
    photographer = models.ForeignKey("accounts.PhotographerProfile", on_delete=models.CASCADE, related_name="store_products")
    gallery = models.ForeignKey(Gallery, on_delete=models.CASCADE, related_name="store_products")
    name = models.CharField(max_length=180)
    product_type = models.CharField(max_length=30, choices=ProductType.choices)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="galleries/products/%Y/%m/", blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    fulfillment = models.CharField(max_length=12, choices=Fulfillment.choices, default=Fulfillment.DIGITAL)
    download_resolution = models.CharField(max_length=12, choices=Resolution.choices, blank=True)
    maximum_download_count = models.PositiveIntegerField(blank=True, null=True)
    active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["display_order", "name"]
    def clean(self):
        errors = {}
        if self.sale_price is not None and self.price is not None and self.sale_price >= self.price:
            errors["sale_price"] = "Sale price must be lower than the regular price."
        if self.store_id and (self.gallery_id != self.store.gallery_id or self.photographer_id != self.store.photographer_id):
            errors["store"] = "Product ownership must match its store."
        if errors: raise ValidationError(errors)


class ProductVariant(models.Model):
    product = models.ForeignKey(StoreProduct, on_delete=models.CASCADE, related_name="variants")
    name = models.CharField(max_length=100)
    price_adjustment = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    class Meta:
        ordering = ["display_order", "name"]
        constraints = [models.UniqueConstraint(fields=["product", "name"], name="store_product_variant_unique")]


class GalleryOrder(models.Model):
    class Status(models.TextChoices):
        PENDING="pending", "Pending"
        PAID="paid", "Paid"
        PROCESSING="processing", "Processing"
        COMPLETED="completed", "Completed"
        CANCELLED="cancelled", "Cancelled"
        REFUNDED="refunded", "Refunded"
    photographer = models.ForeignKey("accounts.PhotographerProfile", on_delete=models.CASCADE, related_name="gallery_orders")
    gallery = models.ForeignKey(Gallery, on_delete=models.PROTECT, related_name="orders")
    store = models.ForeignKey(GalleryStore, on_delete=models.PROTECT, related_name="orders")
    order_number = models.CharField(max_length=30, unique=True)
    customer_name = models.CharField(max_length=160)
    customer_email = models.EmailField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    fulfillment_status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    internal_notes = models.TextField(blank=True)
    activity_history = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta: ordering = ["-created_at"]
    def clean(self):
        if self.store_id and (self.gallery_id != self.store.gallery_id or self.photographer_id != self.store.photographer_id):
            raise ValidationError({"store": "Order ownership must match its store."})


class GalleryOrderItem(models.Model):
    order = models.ForeignKey(GalleryOrder, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(StoreProduct, on_delete=models.SET_NULL, blank=True, null=True, related_name="order_items")
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, blank=True, null=True, related_name="order_items")
    product_name = models.CharField(max_length=180)
    selected_photos = models.ManyToManyField(GalleryPhoto, blank=True, related_name="order_items")
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)


class DiscountCode(models.Model):
    class DiscountType(models.TextChoices):
        PERCENTAGE="percentage", "Percentage"
        FIXED="fixed", "Fixed amount"
    photographer = models.ForeignKey("accounts.PhotographerProfile", on_delete=models.CASCADE, related_name="discount_codes")
    gallery = models.ForeignKey(Gallery, on_delete=models.CASCADE, related_name="discount_codes")
    code = models.CharField(max_length=40)
    discount_type = models.CharField(max_length=12, choices=DiscountType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_order = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    starts_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    usage_limit = models.PositiveIntegerField(blank=True, null=True)
    times_used = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    class Meta:
        ordering = ["-active", "code"]
        constraints = [models.UniqueConstraint(fields=["gallery", "code"], name="gallery_discount_code_unique")]
    def clean(self):
        if self.gallery_id and self.photographer_id and self.gallery.photographer_id != self.photographer_id:
            raise ValidationError({"gallery": "Discount and gallery must have the same photographer."})
        if self.discount_type == self.DiscountType.PERCENTAGE and self.amount > 100:
            raise ValidationError({"amount": "Percentage cannot exceed 100."})


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
