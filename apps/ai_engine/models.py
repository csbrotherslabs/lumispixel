from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Q
from django.utils import timezone


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
    usage_reservation = models.ForeignKey(
        "billing.AIUsageTransaction",
        on_delete=models.PROTECT,
        related_name="ai_jobs",
        blank=True,
        null=True,
        help_text="Current-attempt AI usage reservation. Historical ledger rows remain append-only.",
    )
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

    @staticmethod
    def _extend_update_fields(kwargs, *fields):
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | set(fields)

    def save(self, *args, **kwargs):
        """Keep processing status and AI-credit accounting in one DB transaction.

        Jobs are free while queued. Entering RUNNING reserves one AI action per
        gallery image. COMPLETED settles the reservation; FAILED/CANCELLED
        releases it. Each retry gets a new attempt-scoped idempotency key.
        """
        if self._state.adding or not self.pk:
            return super().save(*args, **kwargs)

        from apps.billing.ai_usage import release_ai_usage, reserve_ai_usage, settle_ai_usage

        terminal_statuses = {self.Status.COMPLETED, self.Status.FAILED, self.Status.CANCELLED}
        with transaction.atomic():
            # Lock only the AIJob row. usage_reservation is nullable, so joining it
            # in the SELECT ... FOR UPDATE query makes PostgreSQL reject the lock
            # when the job does not yet have a reservation. The FK is loaded on
            # demand below after the job row has been safely locked.
            previous = AIJob.objects.select_for_update().get(pk=self.pk)
            entering_running = self.status == self.Status.RUNNING and previous.status != self.Status.RUNNING
            entering_terminal = self.status in terminal_statuses and previous.status not in terminal_statuses

            if entering_running:
                self.attempts = previous.attempts + 1
                self.started_at = self.started_at or timezone.now()
                self.completed_at = None
                image_units = self.gallery.image_count
                if image_units > 0:
                    reservation = reserve_ai_usage(
                        self.photographer,
                        self.task_type,
                        units=image_units,
                        idempotency_key=f"ai-job:{self.pk}:attempt:{self.attempts}:reserve",
                        source_reference=f"ai-job:{self.pk}",
                        metadata={"job_id": self.pk, "gallery_id": self.gallery_id, "attempt": self.attempts},
                    )
                    self.usage_reservation = reservation
                else:
                    self.usage_reservation = None
                self._extend_update_fields(kwargs, "attempts", "started_at", "completed_at", "usage_reservation")

            if entering_terminal:
                reservation = previous.usage_reservation
                if reservation is not None:
                    if self.status == self.Status.COMPLETED:
                        progress = AIProcessingStatus.objects.filter(job_id=self.pk).first()
                        actual_units = reservation.total_units
                        if progress is not None and progress.completed_images > 0:
                            actual_units = min(progress.completed_images, reservation.total_units)
                        settle_ai_usage(
                            reservation,
                            actual_units=actual_units,
                            idempotency_key=f"ai-job:{self.pk}:attempt:{previous.attempts}:settle",
                            metadata={"job_id": self.pk, "status": self.status},
                        )
                    else:
                        release_ai_usage(
                            reservation,
                            idempotency_key=f"ai-job:{self.pk}:attempt:{previous.attempts}:release",
                            metadata={"job_id": self.pk, "status": self.status},
                        )
                self.completed_at = self.completed_at or timezone.now()
                self._extend_update_fields(kwargs, "completed_at")

            return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.gallery} — {self.get_task_type_display()}"


class AIProcessingStatus(models.Model):
    """Mutable progress snapshot kept separate from the immutable job request."""

    job = models.OneToOneField(AIJob, on_delete=models.CASCADE, related_name="progress")
    total_images = models.PositiveIntegerField(default=0)
    completed_images = models.PositiveIntegerField(default=0)
    failed_images = models.PositiveIntegerField(default=0)
    current_stage = models.CharField(max_length=120, blank=True)
    progress_percent = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def clean(self):
        if self.progress_percent > 100:
            raise ValidationError({"progress_percent": "Progress percent cannot exceed 100."})
        if self.completed_images + self.failed_images > self.total_images:
            raise ValidationError("Completed and failed image counts cannot exceed the total image count.")

    def save(self, *args, **kwargs):
        if self.total_images:
            processed = self.completed_images + self.failed_images
            self.progress_percent = min(100, int((processed / self.total_images) * 100))
        else:
            self.progress_percent = 0
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.job} — {self.progress_percent}%"


class AIImageResult(models.Model):
    """Normalized per-image AI output that can be queried independently of the worker."""

    job = models.ForeignKey(AIJob, on_delete=models.CASCADE, related_name="image_results")
    photo = models.ForeignKey("galleries.Photo", on_delete=models.CASCADE, related_name="ai_results")
    result_type = models.CharField(max_length=40)
    score = models.FloatField(blank=True, null=True)
    label = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["photo_id", "id"]
        constraints = [
            models.UniqueConstraint(fields=["job", "photo", "result_type"], name="unique_ai_result_per_job_photo_type"),
        ]

    def __str__(self):
        return f"{self.photo} — {self.result_type}"


class AIGallerySummary(models.Model):
    """A compact aggregate for photographer-facing gallery AI insights."""

    gallery = models.OneToOneField("galleries.Gallery", on_delete=models.CASCADE, related_name="ai_summary")
    blur_count = models.PositiveIntegerField(default=0)
    duplicate_count = models.PositiveIntegerField(default=0)
    closed_eyes_count = models.PositiveIntegerField(default=0)
    face_count = models.PositiveIntegerField(default=0)
    average_quality_score = models.FloatField(blank=True, null=True)
    suggested_keep_count = models.PositiveIntegerField(default=0)
    last_processed_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["gallery_id"]

    def __str__(self):
        return f"AI summary for {self.gallery}"
