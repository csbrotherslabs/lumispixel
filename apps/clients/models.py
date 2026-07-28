from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class PhotographerOwnedQuerySet(models.QuerySet):
    """Query helpers that make workspace scoping explicit and reusable."""

    def for_photographer(self, photographer):
        return self.filter(photographer=photographer)

    def for_user(self, user):
        return self.filter(photographer__user=user)


class PhotographerOwnedModel(models.Model):
    photographer = models.ForeignKey(
        "accounts.PhotographerProfile",
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_records",
    )

    objects = PhotographerOwnedQuerySet.as_manager()

    class Meta:
        abstract = True


class Lead(PhotographerOwnedModel):
    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        CONSULTATION = "consultation", "Consultation"
        PROPOSAL_SENT = "proposal_sent", "Proposal sent"
        BOOKED = "booked", "Booked"
        LOST = "lost", "Lost"

    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    event_type = models.CharField(max_length=100, blank=True)
    event_date = models.DateField(blank=True, null=True)
    lead_source = models.CharField(max_length=100, blank=True)
    estimated_value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    last_contacted_date = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["photographer", "status", "-created_at"], name="lead_owner_status_created"),
            models.Index(fields=["photographer", "event_date"], name="lead_owner_event_date"),
            models.Index(fields=["photographer", "email"], name="lead_owner_email"),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()


class Client(PhotographerOwnedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        ARCHIVED = "archived", "Archived"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="crm_client_records",
        blank=True,
        null=True,
    )
    converted_lead = models.OneToOneField(
        Lead,
        on_delete=models.SET_NULL,
        related_name="converted_client",
        blank=True,
        null=True,
    )
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    company = models.CharField(max_length=200, blank=True)
    address = models.TextField(blank=True)
    birthday = models.DateField(blank=True, null=True)
    tags = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["photographer", "status", "last_name"], name="client_owner_status_name"),
            models.Index(fields=["photographer", "email"], name="client_owner_email"),
        ]

    def clean(self):
        if self.converted_lead_id and self.photographer_id != self.converted_lead.photographer_id:
            raise ValidationError({"converted_lead": "The converted lead must belong to this photographer."})

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()


class ClientNote(PhotographerOwnedModel):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="notes")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["photographer", "client", "-created_at"], name="note_owner_client_created")]

    def clean(self):
        if self.client_id and self.photographer_id != self.client.photographer_id:
            raise ValidationError({"client": "The client must belong to this photographer."})

    def __str__(self):
        return f"Note for {self.client}"


class ClientTask(PhotographerOwnedModel):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    title = models.CharField(max_length=255)
    due_date = models.DateField(blank=True, null=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="tasks", blank=True, null=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="tasks", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_date", "-created_at"]
        indexes = [
            models.Index(fields=["photographer", "status", "due_date"], name="task_owner_status_due"),
            models.Index(fields=["photographer", "priority"], name="task_owner_priority"),
        ]

    def clean(self):
        errors = {}
        if not self.lead_id and not self.client_id:
            errors["lead"] = "A task must be related to a lead or client."
        if self.lead_id and self.photographer_id != self.lead.photographer_id:
            errors["lead"] = "The lead must belong to this photographer."
        if self.client_id and self.photographer_id != self.client.photographer_id:
            errors["client"] = "The client must belong to this photographer."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.title


class ClientActivity(PhotographerOwnedModel):
    class EventType(models.TextChoices):
        LEAD_CREATED = "lead_created", "Lead created"
        NOTE_ADDED = "note_added", "Note added"
        EMAIL_SENT = "email_sent", "Email sent"
        CONSULTATION_SCHEDULED = "consultation_scheduled", "Consultation scheduled"
        LEAD_CONVERTED = "lead_converted", "Lead converted"
        CONTRACT_SIGNED = "contract_signed", "Contract signed"
        INVOICE_SENT = "invoice_sent", "Invoice sent"
        PAYMENT_RECEIVED = "payment_received", "Payment received"
        GALLERY_DELIVERED = "gallery_delivered", "Gallery delivered"

    event_type = models.CharField(max_length=32, choices=EventType.choices)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="activities", blank=True, null=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="activities", blank=True, null=True)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]
        verbose_name_plural = "client activities"
        indexes = [
            models.Index(fields=["photographer", "-occurred_at"], name="activity_owner_occurred"),
            models.Index(fields=["photographer", "event_type", "-occurred_at"], name="activity_owner_type_time"),
        ]

    def clean(self):
        errors = {}
        if self.lead_id and self.photographer_id != self.lead.photographer_id:
            errors["lead"] = "The lead must belong to this photographer."
        if self.client_id and self.photographer_id != self.client.photographer_id:
            errors["client"] = "The client must belong to this photographer."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.get_event_type_display()


class ClientSession(PhotographerOwnedModel):
    class Status(models.TextChoices):
        TENTATIVE = "tentative", "Tentative"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="sessions")
    session_type = models.CharField(max_length=120)
    starts_at = models.DateTimeField()
    location = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.TENTATIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at"]
        indexes = [models.Index(fields=["photographer", "status", "starts_at"], name="session_owner_status_start")]

    def clean(self):
        if self.client_id and self.photographer_id != self.client.photographer_id:
            raise ValidationError({"client": "The client must belong to this photographer."})

    def __str__(self):
        return f"{self.client} — {self.session_type}"


class ClientInvoice(PhotographerOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        PARTIALLY_PAID = "partially_paid", "Partially paid"
        PAID = "paid", "Paid"
        VOID = "void", "Void"

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="invoices")
    total = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_date", "-created_at"]
        indexes = [models.Index(fields=["photographer", "status", "due_date"], name="invoice_owner_status_due")]

    def clean(self):
        errors = {}
        if self.client_id and self.photographer_id != self.client.photographer_id:
            errors["client"] = "The client must belong to this photographer."
        if self.amount_paid > self.total:
            errors["amount_paid"] = "Amount paid cannot exceed the invoice total."
        if errors:
            raise ValidationError(errors)

    @property
    def balance(self):
        return self.total - self.amount_paid
