from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class AIJobQuerySet(models.QuerySet):
    def for_photographer(self, photographer):
        return self.filter(photographer=photographer)

    def active(self):
        return self.filter(status__in=[AIJob.Status.QUEUED, AIJob.Status.RUNNING])


class AIJob(models.Model):
    """A durable, worker-agnostic request to process one gallery."""

    class TaskType(models.TextChoices):
        FACE_DETECTION = "face_detection", "Face Detection"
        FACE_CLUSTERING = "face_clustering", "Face Clustering"
        DUPLICATE_DETECTION = "duplicate_detection", "Duplicate Detection"
        BLUR_DETECTION = "blur_detection", "Blur Detection"
        CLOSED_EYES_DETECTION = "closed_eyes_detection", "Closed Eyes Detection"
        IMAGE_QUALITY_SCORING = "image_quality_scoring", "Image Quality Scoring"
        SCENE_RECOGNITION = "scene_recognition", "Scene Recognition"
        OBJECT_DETECTION = "object_detection", "Object Detection"
        COLOR_DETECTION = "color_detection", "Color Detection"
        KEYWORD_GENERATION = "keyword_generation", "Keyword Generation"
        SEARCH_INDEXING = "search_indexing", "Search Indexing"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    photographer = models.ForeignKey("accounts.PhotographerProfile", on_delete=models.CASCADE, related_name="ai_jobs")
    gallery = models.ForeignKey("galleries.Gallery", on_delete=models.CASCADE, related_name="ai_jobs")
    task_type = models.CharField(max_length=40, choices=TaskType.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    celery_task_id = models.CharField(max_length=255, blank=True, db_index=True, help_text="Reserved for a future background-worker task id.")
    priority = models.PositiveSmallIntegerField(default=5)
    queued_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    estimated_seconds = models.PositiveIntegerField(blank=True, null=True)
    error_summary = models.CharField(max_length=300, blank=True)
    error_details = models.TextField(blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    worker_metadata = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AIJobQuerySet.as_manager()

    class Meta:
        ordering = ["-queued_at"]
        indexes = [
            models.Index(fields=["photographer", "status", "-queued_at"], name="ai_job_owner_status"),
            models.Index(fields=["gallery", "task_type", "status"], name="ai_job_gallery_task"),
        ]

    def clean(self):
        if self.gallery_id and self.photographer_id and self.gallery.photographer_id != self.photographer_id:
            raise ValidationError({"gallery": "Gallery must belong to this photographer."})

    def __str__(self):
        return f"{self.gallery} — {self.get_task_type_display()}"


class AIProcessingStatus(models.Model):
    """Mutable progress snapshot kept separate from the immutable job request."""

    job = models.OneToOneField(AIJob, on_delete=models.CASCADE, related_name="progress")
    total_images = models.PositiveIntegerField(default=0)
    completed_images = models.PositiveIntegerField(default=0)
    failed_images = models.PositiveIntegerField(default=0)
    current_stage = models.CharField(max_length=120, blank=True)
    heartbeat_at = models.DateTimeField(blank=True, null=True, help_text="Future workers can use this to report liveness.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "AI processing statuses"
        constraints = [
            models.CheckConstraint(condition=Q(completed_images__lte=F("total_images")), name="ai_completed_lte_total"),
            models.CheckConstraint(condition=Q(failed_images__lte=F("total_images")), name="ai_failed_lte_total"),
        ]

    @property
    def percent_complete(self):
        return min(round(self.completed_images / self.total_images * 100), 100) if self.total_images else 0

    def __str__(self):
        return f"{self.job} ({self.percent_complete}%)"
