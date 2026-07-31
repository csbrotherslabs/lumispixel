from django.conf import settings
from django.core.exceptions import ValidationError
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
        LEAD_UPDATED = "lead_updated", "Lead updated"
        STAGE_CHANGED = "stage_changed", "Stage changed"
        FOLLOW_UP_CREATED = "follow_up_created", "Follow-up created"
        LEAD_BOOKED = "lead_booked", "Lead booked"
        LEAD_LOST = "lead_lost", "Lead lost"
        LEAD_ARCHIVED = "lead_archived", "Lead archived"
        CLIENT_UPDATED = "client_updated", "Client updated"
        CLIENT_ARCHIVED = "client_archived", "Client archived"
        CLIENT_RESTORED = "client_restored", "Client restored"

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
    duration_minutes = models.PositiveIntegerField(default=120)
    location = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.TENTATIVE)
    booking_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
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

    invoice = models.ForeignKey(ClientInvoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.COMPLETED)
    paid_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["photographer", "status", "paid_at"], name="payment_owner_status_date")]

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
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.COMPLETED)
    refunded_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["photographer", "status", "refunded_at"], name="refund_owner_status_date")]

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
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.APPLIED)
    applied_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["photographer", "status", "applied_at"], name="credit_owner_status_date")]

    def clean(self):
        if self.invoice_id and self.photographer_id != self.invoice.photographer_id:
            raise ValidationError({"invoice": "The invoice must belong to this photographer."})
