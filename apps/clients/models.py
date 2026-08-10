from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage, storages
from django.db import models, transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone


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


class LeadQuerySet(PhotographerOwnedQuerySet):
    """Database-level lead metrics that retain any existing workspace scope."""

    def overdue_followups(self, as_of=None):
        as_of = as_of or timezone.localdate()
        return self.filter(next_follow_up__lt=as_of).exclude(status__in=("booked", "lost"))

    def pipeline_value(self):
        return self.exclude(status="lost").aggregate(
            total=Coalesce(
                Sum("estimated_value"),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )["total"]

    def stage_counts(self):
        counts = {row["status"]: row["count"] for row in self.values("status").annotate(count=Count("pk"))}
        return {value: counts.get(value, 0) for value, _label in Lead.Status.choices}

    def conversion_rate(self):
        total = self.count()
        return (self.filter(status="booked").count() / total * 100) if total else 0.0


class ClientQuerySet(PhotographerOwnedQuerySet):
    """Client workspace queries which keep related records owner-isolated."""

    def active(self):
        return self.filter(status="active")

    def upcoming_sessions(self, as_of=None):
        as_of = as_of or timezone.now()
        return ClientSession.objects.filter(
            client__in=self,
            photographer_id=F("client__photographer_id"),
            starts_at__gte=as_of,
        ).exclude(status=ClientSession.Status.CANCELLED)

    def outstanding_balances(self):
        balance = ExpressionWrapper(
            F("total") - F("amount_paid"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        return ClientInvoice.objects.filter(
            client__in=self,
            photographer_id=F("client__photographer_id"),
        ).exclude(status__in=(ClientInvoice.Status.PAID, ClientInvoice.Status.VOID)).annotate(balance_due=balance)

    def recent_activity(self, since=None):
        activities = ClientActivity.objects.filter(
            client__in=self,
            photographer_id=F("client__photographer_id"),
        )
        return activities.filter(occurred_at__gte=since) if since else activities

    def total_count(self):
        return self.count()

    def monthly_count(self, as_of=None):
        as_of = as_of or timezone.localdate()
        return self.filter(created_at__year=as_of.year, created_at__month=as_of.month).count()

    def total_and_monthly_counts(self, as_of=None):
        return {
            "total": self.total_count(),
            "monthly": self.monthly_count(as_of),
        }


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
    next_follow_up = models.DateField(blank=True, null=True)
    lost_reason = models.CharField(max_length=255, blank=True)
    tags = models.JSONField(default=list, blank=True)
    last_contacted_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True)
    archived_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = LeadQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["photographer", "status", "-created_at"], name="lead_owner_status_created"),
            models.Index(fields=["photographer", "event_date"], name="lead_owner_event_date"),
            models.Index(fields=["photographer", "email"], name="lead_owner_email"),
            models.Index(fields=["photographer", "next_follow_up"], name="lead_owner_followup"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(estimated_value__gte=0) | Q(estimated_value__isnull=True),
                name="lead_estimated_value_nonnegative",
            ),
        ]

    def clean(self):
        errors = {}
        if self.estimated_value is not None and self.estimated_value < 0:
            errors["estimated_value"] = "Estimated value cannot be negative."
        if self.lost_reason and self.status != self.Status.LOST:
            errors["lost_reason"] = "A lost reason can only be set for a lost lead."
        tags_are_valid_list = isinstance(self.tags, list)
        if not tags_are_valid_list or any(not isinstance(tag, str) or not tag.strip() for tag in self.tags):
            errors["tags"] = "Tags must be a list of non-empty strings."
        elif len(self.tags) > 20 or any(len(tag) > 50 for tag in self.tags):
            errors["tags"] = "Use at most 20 tags, each no longer than 50 characters."
        if errors:
            raise ValidationError(errors)

    def convert_to_client(self):
        """Atomically convert this lead once, without crossing workspace boundaries."""
        if not self.pk:
            raise ValidationError("Save the lead before converting it.")
        with transaction.atomic():
            lead = type(self).objects.select_for_update().get(pk=self.pk, photographer=self.photographer)
            if lead.email.strip() and Client.objects.for_photographer(lead.photographer).filter(
                email__iexact=lead.email.strip()
            ).exclude(converted_lead=lead).exists():
                raise ValidationError(
                    "A client with this email address already exists. Open that client instead."
                )
            client, created = Client.objects.get_or_create(
                converted_lead=lead,
                defaults={
                    "photographer": lead.photographer,
                    "first_name": lead.first_name,
                    "last_name": lead.last_name,
                    "email": lead.email,
                    "phone": lead.phone,
                    "tags": list(lead.tags),
                },
            )
            if client.photographer_id != lead.photographer_id:
                raise ValidationError("The converted client must belong to the same photographer.")
            if lead.status != self.Status.BOOKED:
                lead.status = self.Status.BOOKED
                lead.save(update_fields=["status", "updated_at"])
            self.status = lead.status
            return client, created

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()


class Client(PhotographerOwnedModel):
    assigned_members = models.ManyToManyField(
        "dashboard.StudioMembership", blank=True, related_name="assigned_clients"
    )
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        ARCHIVED = "archived", "Archived"

    class ClientType(models.TextChoices):
        INDIVIDUAL = "individual", "Individual"
        BUSINESS = "business", "Business"
        ORGANIZATION = "organization", "Organization"

    class ContactMethod(models.TextChoices):
        EMAIL = "email", "Email"
        PHONE = "phone", "Phone"
        TEXT = "text", "Text message"

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
    lead_source = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    birthday = models.DateField(blank=True, null=True)
    client_type = models.CharField(max_length=20, choices=ClientType.choices, blank=True)
    preferred_contact_method = models.CharField(max_length=10, choices=ContactMethod.choices, blank=True)
    tags = models.JSONField(default=list, blank=True)
    profile_photo = models.ImageField(upload_to="clients/profile_photos/%Y/%m/", blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ClientQuerySet.as_manager()

    class Meta:
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["photographer", "status", "last_name"], name="client_owner_status_name"),
            models.Index(fields=["photographer", "email"], name="client_owner_email"),
            models.Index(fields=["photographer", "-created_at"], name="client_owner_created"),
            models.Index(fields=["photographer", "client_type"], name="client_owner_type"),
        ]

    def clean(self):
        errors = {}
        if self.converted_lead_id and self.photographer_id != self.converted_lead.photographer_id:
            errors["converted_lead"] = "The converted lead must belong to this photographer."
        if not isinstance(self.tags, list) or any(not isinstance(tag, str) or not tag.strip() for tag in self.tags):
            errors["tags"] = "Tags must be a list of non-empty strings."
        elif len(self.tags) > 20 or any(len(tag) > 50 for tag in self.tags):
            errors["tags"] = "Use at most 20 tags, each no longer than 50 characters."
        if self.preferred_contact_method == self.ContactMethod.EMAIL and not self.email:
            errors["preferred_contact_method"] = "An email address is required for email contact."
        if self.preferred_contact_method in (self.ContactMethod.PHONE, self.ContactMethod.TEXT) and not self.phone:
            errors["preferred_contact_method"] = "A phone number is required for phone or text contact."
        if self.birthday and self.birthday > timezone.localdate():
            errors["birthday"] = "Birthday cannot be in the future."
        if self.profile_photo and self.profile_photo.size > 5 * 1024 * 1024:
            errors["profile_photo"] = "Profile photos must be 5 MB or smaller."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()


class ClientNote(PhotographerOwnedModel):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="client_notes",
        blank=True,
        null=True,
    )
    content = models.TextField(max_length=5000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["photographer", "client", "-created_at"], name="note_owner_client_created")]

    def clean(self):
        errors = {}
        if self.client_id and self.photographer_id != self.client.photographer_id:
            errors["client"] = "The client must belong to this photographer."
        if not self.content or not self.content.strip():
            errors["content"] = "Enter a note before saving."
        if errors:
            raise ValidationError(errors)

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
        LEAD_UPDATED = "lead_updated", "Lead updated"
        STAGE_CHANGED = "stage_changed", "Stage changed"
        FOLLOW_UP_CREATED = "follow_up_created", "Follow-up created"
        LEAD_BOOKED = "lead_booked", "Lead booked"
        LEAD_LOST = "lead_lost", "Lead lost"
        LEAD_ARCHIVED = "lead_archived", "Lead archived"
        CLIENT_UPDATED = "client_updated", "Client updated"
        CLIENT_ARCHIVED = "client_archived", "Client archived"
        CLIENT_RESTORED = "client_restored", "Client restored"
        BOOKING_CREATED = "booking_created", "Booking created"
        BOOKING_UPDATED = "booking_updated", "Booking updated"
        BOOKING_RESCHEDULED = "booking_rescheduled", "Booking rescheduled"
        BOOKING_CANCELLED = "booking_cancelled", "Booking cancelled"

    event_type = models.CharField(max_length=32, choices=EventType.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="client_activities",
        blank=True,
        null=True,
    )
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="activities", blank=True, null=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="activities", blank=True, null=True)
    booking = models.ForeignKey("ClientSession", on_delete=models.CASCADE, related_name="activities", blank=True, null=True)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at", "-pk"]
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
        if self.booking_id and self.photographer_id != self.booking.photographer_id:
            errors["booking"] = "The booking must belong to this photographer."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.get_event_type_display()


class ClientSession(PhotographerOwnedModel):
    assigned_members = models.ManyToManyField(
        "dashboard.StudioMembership", blank=True, related_name="assigned_bookings"
    )
    class Status(models.TextChoices):
        TENTATIVE = "tentative", "Tentative"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class EventKind(models.TextChoices):
        BOOKING = "booking", "Booking"
        CONSULTATION = "consultation", "Consultation"

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="sessions")
    event_kind = models.CharField(max_length=16, choices=EventKind.choices, default=EventKind.BOOKING)
    session_type = models.CharField(max_length=120)
    starts_at = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=120)
    location = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.TENTATIVE)
    booking_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    # Reporting uses the business event date, not the row creation date.  Keeping
    # this separate also means a tentative request confirmed later lands in the
    # correct growth period.
    confirmed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancellation_reason = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["starts_at"]
        indexes = [
            models.Index(fields=["photographer", "status", "starts_at"], name="session_owner_status_start"),
            models.Index(fields=["photographer", "status", "confirmed_at"], name="session_owner_confirmed"),
        ]

    def save(self, *args, **kwargs):
        if self.status in (self.Status.CONFIRMED, self.Status.COMPLETED) and self.confirmed_at is None:
            self.confirmed_at = timezone.now()
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"confirmed_at"}
        super().save(*args, **kwargs)

    def clean(self):
        if self.client_id and self.photographer_id != self.client.photographer_id:
            raise ValidationError({"client": "The client must belong to this photographer."})

    def __str__(self):
        return f"{self.client} — {self.session_type}"


class ContractTemplate(PhotographerOwnedModel):
    """Reusable, studio-owned source content for booking contracts."""

    class Category(models.TextChoices):
        GENERAL = "general", "General"
        WEDDING = "wedding", "Wedding"
        PORTRAIT = "portrait", "Portrait"
        EVENT = "event", "Event"
        COMMERCIAL = "commercial", "Commercial"
        ADDENDUM = "addendum", "Addendum"

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    title = models.CharField(max_length=200)
    content = models.TextField()
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.GENERAL)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_contract_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "pk")
        indexes = [models.Index(fields=("photographer", "is_active"), name="contract_tpl_owner_active")]

    def clean(self):
        errors = {}
        if not self.name.strip():
            errors["name"] = "Enter a template name."
        if not self.title.strip():
            errors["title"] = "Enter a contract title."
        if not self.content.strip():
            errors["content"] = "Enter contract content."
        if self.version < 1:
            errors["version"] = "Version must be at least 1."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.name


class Contract(PhotographerOwnedModel):
    """An independently editable snapshot of an agreement for one booking."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready"
        SENT = "sent", "Sent"
        VIEWED = "viewed", "Viewed"
        SIGNED = "signed", "Signed"
        VOIDED = "voided", "Voided"

    booking = models.ForeignKey(ClientSession, on_delete=models.PROTECT, related_name="contracts")
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="contracts")
    template = models.ForeignKey(
        ContractTemplate, on_delete=models.SET_NULL, null=True, related_name="contracts",
    )
    title = models.CharField(max_length=200)
    content = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    version = models.PositiveIntegerField(default=1)
    sent_at = models.DateTimeField(null=True, blank=True)
    viewed_at = models.DateTimeField(null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    rendered_content = models.TextField(blank=True)
    review_token_digest = models.CharField(max_length=64, blank=True, editable=False, db_index=True)
    review_token_expires_at = models.DateTimeField(null=True, blank=True)
    review_token_revoked_at = models.DateTimeField(null=True, blank=True)
    sent_to_email = models.EmailField(blank=True)
    send_count = models.PositiveIntegerField(default=0)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_contracts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        indexes = [
            models.Index(fields=("photographer", "booking", "-created_at"), name="contract_owner_booking"),
            models.Index(fields=("photographer", "status"), name="contract_owner_status"),
        ]

    def clean(self):
        errors = {}
        if self.booking_id:
            if self.photographer_id != self.booking.photographer_id:
                errors["booking"] = "The booking must belong to this photographer."
            if self.client_id and self.client_id != self.booking.client_id:
                errors["client"] = "The contract client must match the booking client."
        if self.client_id and self.photographer_id != self.client.photographer_id:
            errors["client"] = "The client must belong to this photographer."
        if self.template_id and self.photographer_id != self.template.photographer_id:
            errors["template"] = "The template must belong to this photographer."
        if not self.title.strip():
            errors["title"] = "Enter a contract title."
        if not self.content.strip():
            errors["content"] = "Enter contract content."
        if self.version < 1:
            errors["version"] = "Version must be at least 1."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """Keep the legal snapshot immutable once it has been delivered."""
        if self.pk:
            persisted = type(self).objects.filter(pk=self.pk).values(
                "locked_at", "status", "photographer_id", "booking_id", "client_id",
                "template_id", "title", "content", "version", "rendered_content",
            ).first()
            if persisted and persisted["locked_at"]:
                protected = (
                    "photographer_id", "booking_id", "client_id", "template_id", "title",
                    "content", "version", "rendered_content",
                )
                update_fields = kwargs.get("update_fields")
                checked = protected if update_fields is None else tuple(
                    field for field in protected if field.removesuffix("_id") in update_fields or field in update_fields
                )
                if any(getattr(self, field) != persisted[field] for field in checked):
                    raise ValidationError("A delivered contract is locked. Create a new contract for revised terms.")
                if persisted["status"] == self.Status.SIGNED and self.status != self.Status.SIGNED:
                    raise ValidationError("A signed contract's status cannot be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status == self.Status.SIGNED:
            raise ValidationError("A signed contract cannot be deleted.")
        return super().delete(*args, **kwargs)


class ContractEvent(models.Model):
    """Append-only evidence for material contract lifecycle events."""

    class EventType(models.TextChoices):
        CREATED = "created", "Created"
        SENT = "sent", "Sent"
        RESENT = "resent", "Resent"
        VIEWED = "viewed", "Viewed"
        SIGNED = "signed", "Signed"

    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="contract_events",
    )
    event_type = models.CharField(max_length=24, choices=EventType.choices)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-occurred_at", "-pk")
        indexes = [models.Index(fields=("contract", "-occurred_at"), name="contract_event_time")]


class ContractSignature(models.Model):
    """Immutable first-party evidence of one electronic acceptance event."""

    class SignatureType(models.TextChoices):
        TYPED = "typed", "Typed signature"

    contract = models.OneToOneField(Contract, on_delete=models.PROTECT, related_name="signature")
    signer_name = models.CharField(max_length=200)
    signature_value = models.CharField(max_length=200)
    signature_type = models.CharField(max_length=16, choices=SignatureType.choices, default=SignatureType.TYPED)
    consent_accepted = models.BooleanField()
    consent_text = models.TextField()
    signed_at = models.DateTimeField()
    content_hash = models.CharField(max_length=64, editable=False)
    contract_version = models.PositiveIntegerField()
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="contract_signatures")
    photographer = models.ForeignKey(
        "accounts.PhotographerProfile", on_delete=models.PROTECT, related_name="contract_signatures",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True, editable=False)
    user_agent = models.CharField(max_length=512, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    signed_snapshot = models.JSONField(default=dict, editable=False)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Signature evidence is immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Signature evidence cannot be deleted.")


def signed_contract_document_path(instance, filename):
    """Use an opaque, tenant-partitioned key; storage decides its physical location."""
    return f"contracts/{instance.contract.photographer_id}/{instance.contract_id}/{filename}"


def contract_document_storage():
    """Resolve an optional object-storage alias, with private development storage as fallback."""
    if "contract_documents" in getattr(settings, "STORAGES", {}):
        return storages["contract_documents"]
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


class SignedContractDocument(models.Model):
    """Private generated copy of one immutable signed contract snapshot."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    contract = models.OneToOneField(Contract, on_delete=models.PROTECT, related_name="signed_document")
    file = models.FileField(storage=contract_document_storage, upload_to=signed_contract_document_path,
                            blank=True, max_length=500)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    generated_at = models.DateTimeField(null=True, blank=True)
    content_type = models.CharField(max_length=100, default="application/pdf")
    file_size = models.PositiveBigIntegerField(default=0)
    file_hash = models.CharField(max_length=64, blank=True, editable=False)
    signed_content_hash = models.CharField(max_length=64, editable=False)
    error_message = models.CharField(max_length=255, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=("status", "updated_at"), name="signed_doc_status_time")]

    def save(self, *args, **kwargs):
        if self.pk:
            persisted = type(self).objects.filter(pk=self.pk).values(
                "status", "contract_id", "file", "generated_at", "file_size", "file_hash",
                "signed_content_hash",
            ).first()
            if persisted and persisted["status"] == self.Status.READY:
                protected = ("contract_id", "file", "generated_at", "file_size", "file_hash",
                             "signed_content_hash")
                if any(str(getattr(self, field)) != str(persisted[field]) for field in protected):
                    raise ValidationError("A completed signed contract PDF cannot be overwritten.")
                if self.status != self.Status.READY:
                    raise ValidationError("A completed signed contract PDF cannot be replaced.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status == self.Status.READY:
            raise ValidationError("A completed signed contract PDF cannot be deleted.")
        return super().delete(*args, **kwargs)


class MiniSession(PhotographerOwnedModel):
    """A tenant-owned schedule block whose bookable children are ``MiniSessionSlot`` rows."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CANCELLED = "cancelled", "Cancelled"

    assigned_members = models.ManyToManyField(
        "dashboard.StudioMembership", blank=True, related_name="assigned_mini_sessions"
    )
    name = models.CharField(max_length=120)
    starts_at = models.DateTimeField()
    slot_duration_minutes = models.PositiveSmallIntegerField()
    slot_count = models.PositiveSmallIntegerField()
    buffer_minutes = models.PositiveSmallIntegerField(default=0)
    capacity_per_slot = models.PositiveSmallIntegerField(default=1)
    location = models.CharField(max_length=255)
    service = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("starts_at", "pk")
        indexes = [models.Index(fields=("photographer", "status", "starts_at"), name="mini_owner_status_start")]

    @property
    def duration_minutes(self):
        return self.slot_count * self.slot_duration_minutes + max(0, self.slot_count - 1) * self.buffer_minutes

    def clean(self):
        if self.slot_duration_minutes < 1 or self.slot_count < 1 or self.capacity_per_slot < 1:
            raise ValidationError("Slot duration, count, and capacity must be positive.")


class MiniSessionSlot(models.Model):
    mini_session = models.ForeignKey(MiniSession, on_delete=models.CASCADE, related_name="slots")
    starts_at = models.DateTimeField()
    duration_minutes = models.PositiveSmallIntegerField()
    position = models.PositiveSmallIntegerField()
    clients = models.ManyToManyField(Client, through="MiniSessionSlotBooking", related_name="mini_session_slots")
    cancelled_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("position",)
        constraints = [
            models.UniqueConstraint(fields=("mini_session", "position"), name="mini_slot_parent_position_unique"),
            models.UniqueConstraint(fields=("mini_session", "starts_at"), name="mini_slot_parent_start_unique"),
        ]


class MiniSessionSlotBooking(PhotographerOwnedModel):
    slot = models.ForeignKey(MiniSessionSlot, on_delete=models.CASCADE, related_name="bookings")
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="mini_session_bookings")
    created_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("slot", "client"), name="mini_slot_client_unique")]

    def clean(self):
        errors = {}
        if self.slot_id and self.photographer_id != self.slot.mini_session.photographer_id:
            errors["slot"] = "The slot must belong to this workspace."
        if self.client_id and self.photographer_id != self.client.photographer_id:
            errors["client"] = "The client must belong to this workspace."
        if errors:
            raise ValidationError(errors)


class ClientInvoice(PhotographerOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        PARTIALLY_PAID = "partially_paid", "Partially paid"
        PAID = "paid", "Paid"
        VOID = "void", "Void"

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="invoices")
    booking = models.ForeignKey(ClientSession, on_delete=models.SET_NULL, related_name="invoices", blank=True, null=True)
    invoice_number = models.CharField(max_length=32, null=True)
    issue_date = models.DateField(default=timezone.localdate)
    currency = models.CharField(max_length=3, default="USD")
    payment_terms = models.PositiveSmallIntegerField(default=30)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    client_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    terms = models.TextField(blank=True)
    delivery_email = models.BooleanField(default=True)
    reminders_enabled = models.BooleanField(default=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_date", "-created_at"]
        indexes = [models.Index(fields=["photographer", "status", "due_date"], name="invoice_owner_status_due")]
        constraints = [models.UniqueConstraint(fields=["photographer", "invoice_number"], name="invoice_owner_number_unique")]

    def clean(self):
        errors = {}
        if self.client_id and self.photographer_id != self.client.photographer_id:
            errors["client"] = "The client must belong to this photographer."
        if self.booking_id and (self.photographer_id != self.booking.photographer_id or self.client_id != self.booking.client_id):
            errors["booking"] = "The booking must belong to this client and photographer."
        if self.total < 0 or self.subtotal < 0 or self.discount_total < 0 or self.tax_total < 0:
            errors["total"] = "Invoice amounts cannot be negative."
        if self.amount_paid > self.total:
            errors["amount_paid"] = "Amount paid cannot exceed the invoice total."
        if errors:
            raise ValidationError(errors)

    @property
    def balance(self):
        return self.total - self.amount_paid

    @property
    def is_locked(self):
        return self.status in (self.Status.PAID, self.Status.VOID)


class InvoiceLineItem(models.Model):
    class ItemType(models.TextChoices):
        PACKAGE = "package", "Booking package"
        SESSION = "session", "Session fee"
        DEPOSIT = "deposit", "Deposit"
        ADD_ON = "add_on", "Add-on"
        TRAVEL = "travel", "Travel fee"
        PRODUCT = "product", "Prints or products"
        CUSTOM = "custom", "Custom item"

    invoice = models.ForeignKey(ClientInvoice, on_delete=models.CASCADE, related_name="line_items")
    item_type = models.CharField(max_length=16, choices=ItemType.choices, default=ItemType.CUSTOM)
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "pk"]


class InvoicePaymentSchedule(models.Model):
    invoice = models.ForeignKey(ClientInvoice, on_delete=models.CASCADE, related_name="payment_schedule")
    label = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField()
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "due_date"]


class InvoiceActivity(PhotographerOwnedModel):
    invoice = models.ForeignKey(ClientInvoice, on_delete=models.CASCADE, related_name="activity")
    action = models.CharField(max_length=32)
    description = models.CharField(max_length=255)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]


class InvoicePayment(PhotographerOwnedModel):
    """An actual cash movement received against an invoice."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    class Method(models.TextChoices):
        CARD = "card", "Card"
        BANK_TRANSFER = "bank_transfer", "Bank transfer"
        CASH = "cash", "Cash"
        CHECK = "check", "Check"
        EXTERNAL = "external", "External payment"
        OTHER = "other", "Other"

    invoice = models.ForeignKey(ClientInvoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.OTHER)
    external_reference = models.CharField(max_length=120, blank=True)
    processor_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    internal_note = models.TextField(blank=True)
    submission_key = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.COMPLETED)
    paid_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["photographer", "status", "paid_at"], name="payment_owner_status_date")]
        constraints = [models.UniqueConstraint(fields=["photographer", "submission_key"], condition=~Q(submission_key=""), name="payment_owner_submission_unique")]

    def clean(self):
        if self.invoice_id and self.photographer_id != self.invoice.photographer_id:
            raise ValidationError({"invoice": "The invoice must belong to this photographer."})


class PaymentRefund(PhotographerOwnedModel):
    """Cash returned for a payment; credits are deliberately modelled separately."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    payment = models.ForeignKey(InvoicePayment, on_delete=models.CASCADE, related_name="refunds")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=255, default="")
    internal_note = models.TextField(blank=True)
    submission_key = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.COMPLETED)
    refunded_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["photographer", "status", "refunded_at"], name="refund_owner_status_date")]
        constraints = [models.UniqueConstraint(fields=["photographer", "submission_key"], condition=~Q(submission_key=""), name="refund_owner_submission_unique")]

    def clean(self):
        if self.payment_id and self.photographer_id != self.payment.photographer_id:
            raise ValidationError({"payment": "The payment must belong to this photographer."})


class InvoiceCredit(PhotographerOwnedModel):
    """Non-cash value applied to an invoice."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPLIED = "applied", "Applied"
        VOID = "void", "Void"

    invoice = models.ForeignKey(ClientInvoice, on_delete=models.CASCADE, related_name="credits")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    original_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remaining_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reason = models.CharField(max_length=255, default="")
    expires_at = models.DateField(blank=True, null=True)
    internal_note = models.TextField(blank=True)
    submission_key = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.APPLIED)
    applied_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["photographer", "status", "applied_at"], name="credit_owner_status_date")]
        constraints = [
            models.CheckConstraint(condition=Q(remaining_amount__gte=0), name="credit_remaining_nonnegative"),
            models.CheckConstraint(condition=Q(remaining_amount__lte=F("original_amount")), name="credit_remaining_not_over_original"),
            models.UniqueConstraint(fields=["photographer", "submission_key"], condition=~Q(submission_key=""), name="credit_owner_submission_unique"),
        ]

    def clean(self):
        if self.invoice_id and self.photographer_id != self.invoice.photographer_id:
            raise ValidationError({"invoice": "The invoice must belong to this photographer."})
