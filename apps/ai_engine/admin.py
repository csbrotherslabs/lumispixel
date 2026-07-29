from django.contrib import admin

from .models import AIJob, AIProcessingStatus


class AIProcessingStatusInline(admin.StackedInline):
    model = AIProcessingStatus
    extra = 0


@admin.register(AIJob)
class AIJobAdmin(admin.ModelAdmin):
    list_display = ("gallery", "task_type", "status", "queued_at", "completed_at")
    list_filter = ("status", "task_type")
    search_fields = ("gallery__name", "celery_task_id", "error_summary")
    readonly_fields = ("queued_at", "updated_at")
    inlines = (AIProcessingStatusInline,)
