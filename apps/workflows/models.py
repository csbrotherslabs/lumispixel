from django.db import models


class AutomationRule(models.Model):
    class Trigger(models.TextChoices):
        BOOKING_CONFIRMED = "booking_confirmed", "Booking confirmed"
        CONTRACT_SIGNED = "contract_signed", "Contract signed"
        INVOICE_DUE = "invoice_due", "Invoice due"
        PAYMENT_RECEIVED = "payment_received", "Payment received"
        SHOOT_COMPLETED = "shoot_completed", "Shoot completed"
        GALLERY_PUBLISHED = "gallery_published", "Gallery published"
        GALLERY_EXPIRING = "gallery_expiring", "Gallery nearing expiration"

    class Action(models.TextChoices):
        SEND_CONTRACT = "send_contract", "Send contract"
        PREPARE_INVOICE = "prepare_invoice", "Prepare invoice"
        SEND_INVOICE_REMINDER = "send_invoice_reminder", "Send invoice reminder"
        COMPLETE_FINANCIAL_WORKFLOW = "complete_financial_workflow", "Complete financial workflow"
        CREATE_GALLERY_TASK = "create_gallery_task", "Create gallery task"
        NOTIFY_GALLERY_CLIENT = "notify_gallery_client", "Notify gallery client"
        SEND_GALLERY_EXPIRATION_REMINDER = "send_gallery_expiration_reminder", "Send gallery expiration reminder"

    photographer = models.ForeignKey(
        "accounts.PhotographerProfile",
        on_delete=models.CASCADE,
        related_name="automation_rules",
    )
    name = models.CharField(max_length=160)
    description = models.CharField(max_length=500, blank=True)
    trigger = models.CharField(max_length=40, choices=Trigger.choices)
    action = models.CharField(max_length=48, choices=Action.choices)
    enabled = models.BooleanField(default=False)
    config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["photographer", "trigger", "action"],
                name="unique_workflow_rule_per_photographer",
            )
        ]

    def __str__(self):
        return self.name


class AutomationExecution(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        SKIPPED = "skipped", "Skipped"
        FAILED = "failed", "Failed"

    rule = models.ForeignKey(AutomationRule, on_delete=models.CASCADE, related_name="executions")
    photographer = models.ForeignKey(
        "accounts.PhotographerProfile",
        on_delete=models.CASCADE,
        related_name="automation_executions",
    )
    event_key = models.CharField(max_length=255)
    trigger = models.CharField(max_length=40, choices=AutomationRule.Trigger.choices)
    target_type = models.CharField(max_length=80)
    target_id = models.PositiveBigIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    message = models.CharField(max_length=500, blank=True)
    error = models.TextField(blank=True)
    context = models.JSONField(default=dict, blank=True)
    queued_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-queued_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["rule", "event_key"], name="unique_workflow_execution_event")
        ]
        indexes = [
            models.Index(fields=["photographer", "-queued_at"], name="workflow_owner_queued"),
            models.Index(fields=["status", "-queued_at"], name="workflow_status_queued"),
        ]

    def __str__(self):
        return f"{self.rule.name}: {self.get_status_display()}"
