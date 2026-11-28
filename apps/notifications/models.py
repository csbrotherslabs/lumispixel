from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    class Category(models.TextChoices):
        GALLERY = "gallery", "Gallery"
        DOWNLOAD = "download", "Download"
        PAYMENT = "payment", "Payment"
        MESSAGE = "message", "Message"
        SECURITY = "security", "Security"
        SYSTEM = "system", "System"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.SYSTEM)
    title = models.CharField(max_length=160)
    message = models.TextField(max_length=1000)
    action_url = models.CharField(max_length=500, blank=True)
    action_label = models.CharField(max_length=60, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        indexes = [
            models.Index(fields=("recipient", "is_read", "-created_at"), name="notify_rec_read_created"),
            models.Index(fields=("recipient", "category", "-created_at"), name="notify_rec_cat_created"),
        ]

    def __str__(self):
        return f"{self.recipient}: {self.title}"

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=("is_read", "read_at"))

    def mark_unread(self):
        if self.is_read:
            self.is_read = False
            self.read_at = None
            self.save(update_fields=("is_read", "read_at"))

    @property
    def safe_action_url(self):
        return self.action_url if self.action_url.startswith("/") and not self.action_url.startswith("//") else ""


class NotificationEventReceipt(models.Model):
    """A delivery receipt survives dismissal so retries cannot recreate a notice."""
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event_key = models.CharField(max_length=64)
    notification = models.ForeignKey(Notification, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("recipient", "event_key"), name="notification_recipient_event")]


class EmailDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RETRY = "retry", "Retry scheduled"
        SENT = "sent", "Sent"
        SENDING = "sending", "Sending"
        UNCERTAIN = "uncertain", "Outcome uncertain"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"
        DEAD = "dead", "Dead letter"
        FAILED = "failed", "Failed"  # legacy terminal state

    class FailureKind(models.TextChoices):
        NONE = "", "None"
        TRANSIENT = "transient", "Transient"
        PERMANENT = "permanent", "Permanent"
        UNKNOWN = "unknown", "Unknown"

    idempotency_key = models.CharField(max_length=64, unique=True)
    event_key = models.CharField(max_length=255, db_index=True)
    subject = models.CharField(max_length=255)
    plain_body = models.TextField()
    html_body = models.TextField(blank=True)
    recipients = models.JSONField(default=list)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    lifecycle_kind = models.CharField(max_length=64, blank=True, default="")
    lifecycle_context = models.JSONField(default=dict, blank=True)
    sensitive = models.BooleanField(default=False)
    encrypted_payload = models.TextField(blank=True, default='')
    supersession_scope = models.CharField(max_length=64, blank=True, default='', db_index=True)
    payload_purged_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    attempt_limit = models.PositiveIntegerField(default=6)
    failure_kind = models.CharField(max_length=12, choices=FailureKind.choices, blank=True, default="")
    last_error = models.TextField(blank=True)
    last_attempt_at = models.DateTimeField(blank=True, null=True)
    next_attempt_at = models.DateTimeField(blank=True, null=True, db_index=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    dead_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "pk")
        indexes = [
            models.Index(fields=("status", "created_at"), name="email_delivery_queue"),
            models.Index(fields=("status", "next_attempt_at"), name="email_delivery_retry"),
        ]


class BrevoEmailEvent(models.Model):
    """Minimal provider evidence; no message body, subject, link or recipient plaintext."""
    fingerprint = models.CharField(max_length=64, unique=True)
    delivery = models.ForeignKey(EmailDelivery, null=True, on_delete=models.SET_NULL, related_name="brevo_events")
    event = models.CharField(max_length=32, db_index=True)
    provider_message_id = models.CharField(max_length=255)
    recipient_hash = models.CharField(max_length=64)
    occurred_at = models.PositiveBigIntegerField()
    received_at = models.DateTimeField(auto_now_add=True)


class EmailSupersession(models.Model):
    scope = models.CharField(max_length=64, primary_key=True)
    current = models.ForeignKey(EmailDelivery, null=True, on_delete=models.SET_NULL)


class EmailAttempt(models.Model):
    delivery = models.ForeignKey(EmailDelivery, on_delete=models.PROTECT, related_name="attempt_history")
    number = models.PositiveIntegerField()
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True)
    outcome = models.CharField(max_length=32, default="sending")
    transport = models.CharField(max_length=16, default="smtp")
    provider_message_id = models.CharField(max_length=255, blank=True, db_index=True)
    error_code = models.CharField(max_length=128, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["delivery", "number"], name="unique_email_attempt_number")]


class EmailRecoveryEvent(models.Model):
    delivery = models.ForeignKey(EmailDelivery, on_delete=models.PROTECT)
    actor_id = models.CharField(max_length=128)
    reason = models.CharField(max_length=500)
    previous_attempt_limit = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)


class EmailIntent(models.Model):
    """Explicit communication obligation; never stores a message or raw token."""
    key = models.CharField(max_length=64, unique=True)
    event_key = models.CharField(max_length=255, db_index=True)
    kind = models.CharField(max_length=64, blank=True)
    delivery = models.OneToOneField(EmailDelivery, null=True, blank=True, on_delete=models.PROTECT, related_name="intent")
    created_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=500, blank=True)
    cancelled_by = models.CharField(max_length=128, blank=True)
