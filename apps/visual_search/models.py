import uuid
from django.db import models
from django.db.models import Q


class ConsentPolicyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if "processing_authorized" in kwargs:
            raise ValueError("Use GalleryFaceSearchPolicy.save() to change processing consent")
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        if "processing_authorized" in fields:
            raise ValueError("Use GalleryFaceSearchPolicy.save() to change processing consent")
        return super().bulk_update(objs, fields, batch_size=batch_size)


class GalleryFaceSearchPolicy(models.Model):
    """Explicit photographer authorization; global discovery is independently opt-in."""

    objects = ConsentPolicyQuerySet.as_manager()

    gallery = models.OneToOneField(
        "galleries.Gallery", on_delete=models.CASCADE, related_name="face_search_policy"
    )
    processing_authorized = models.BooleanField(default=False)
    global_discovery_enabled = models.BooleanField(default=False)
    authorized_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(processing_authorized=True) | Q(global_discovery_enabled=False),
                name="visual_discovery_requires_consent",
            ),
        ]

    def save(self, *args, **kwargs):
        # Persist consent-dependent discovery changes even for partial saves.
        if not self.processing_authorized:
            self.global_discovery_enabled = False
            fields = kwargs.get("update_fields")
            if fields is not None:
                kwargs["update_fields"] = set(fields) | {"global_discovery_enabled"}
        return super().save(*args, **kwargs)


class FaceIndexJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    photo = models.ForeignKey(
        "galleries.GalleryPhoto", on_delete=models.CASCADE, related_name="face_index_jobs"
    )
    source_key = models.CharField(max_length=700)
    source_version = models.PositiveIntegerField(default=1)
    model_version = models.CharField(max_length=80, default="arcface-buffalo-l-v1")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    claim_token = models.UUIDField(null=True, blank=True, editable=False)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["photo", "source_version", "model_version"],
                name="visual_face_job_unique_version",
            ),
            models.CheckConstraint(condition=Q(source_version__gte=1), name="visual_face_version_positive"),
        ]
        indexes = [models.Index(fields=["status", "created_at"], name="visual_face_job_pending")]


class FaceVectorPurge(models.Model):
    """Durable, idempotent deletion request in the primary database."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"

    kind = models.CharField(max_length=10, choices=[("photo", "Photo"), ("gallery", "Gallery")])
    object_id = models.BigIntegerField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    claim_token = models.UUIDField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["status", "created_at"], name="visual_purge_pending")]
