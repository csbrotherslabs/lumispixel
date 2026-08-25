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
