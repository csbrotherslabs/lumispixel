from django.db import models
from django.utils import timezone


class AutomationJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RETRY = "retry", "Retry"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    photographer = models.ForeignKey("accounts.PhotographerProfile", on_delete=models.PROTECT)
    kind = models.CharField(max_length=100)
    event_key = models.CharField(max_length=255)
    target_id = models.PositiveBigIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)
    available_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=100, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["photographer", "kind", "event_key"], name="platform_job_event_unique")]
        indexes = [models.Index(fields=["status", "available_at"], name="platform_job_due_idx")]


class AutomationAttempt(models.Model):
    job = models.ForeignKey(AutomationJob, on_delete=models.PROTECT, related_name="history")
    number = models.PositiveIntegerField()
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField()
    outcome = models.CharField(max_length=16)
    error_code = models.CharField(max_length=100, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["job", "number"], name="platform_job_attempt_unique")]
