import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def support_ticket_reference():
    return f"LP-{uuid.uuid4().hex[:8].upper()}"


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.SlugField(max_length=60, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class InternalRole(models.Model):
    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=80, unique=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="roles", null=True, blank=True, help_text="Leave blank for company-wide roles such as Executive or Administrator.")
    description = models.TextField(blank=True)
    is_executive = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("department__name", "name")

    def __str__(self):
        return self.name


class EmployeeProfile(models.Model):
    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACTIVE = "active", "Active"
        LEAVE = "leave", "On leave"
        SUSPENDED = "suspended", "Suspended"
        TERMINATED = "terminated", "Terminated"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="employee_profile")
    employee_id = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=120, blank=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="employees", null=True, blank=True)
    role = models.ForeignKey(InternalRole, on_delete=models.PROTECT, related_name="employees", null=True, blank=True)
    manager = models.ForeignKey("self", on_delete=models.SET_NULL, related_name="direct_reports", null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INVITED)
    hire_date = models.DateField(null=True, blank=True)
    last_internal_access_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("user__last_name", "user__first_name", "user__email")

    def __str__(self):
        return f"{self.user.display_name} ({self.employee_id})"

    @property
    def can_access_internal(self):
        return self.status == self.Status.ACTIVE and self.user.can_login

    def record_access(self):
        self.last_internal_access_at = timezone.now()
        self.save(update_fields=["last_internal_access_at", "updated_at"])


class InternalAuditEvent(models.Model):
    class Category(models.TextChoices):
        ACCESS = "access", "Access"
        EMPLOYEE = "employee", "Employee"
        CUSTOMER = "customer", "Customer"
        BILLING = "billing", "Billing"
        AI = "ai", "AI"
        SUPPORT = "support", "Support"
        SECURITY = "security", "Security"
        SYSTEM = "system", "System"

    actor = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, related_name="audit_events", null=True, blank=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    action = models.CharField(max_length=120)
    target_type = models.CharField(max_length=80, blank=True)
    target_id = models.CharField(max_length=100, blank=True)
    summary = models.CharField(max_length=255)
    reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("category", "created_at"), name="internal_audit_cat_idx"), models.Index(fields=("actor", "created_at"), name="internal_audit_actor_idx")]

    def __str__(self):
        return f"{self.get_category_display()}: {self.summary}"


class SupportTicket(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        WAITING_CUSTOMER = "waiting_customer", "Waiting on customer"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class Category(models.TextChoices):
        ACCOUNT = "account", "Account & access"
        BILLING = "billing", "Billing & plan"
        GALLERIES = "galleries", "Galleries & delivery"
        AI = "ai", "AI tools"
        EDITING = "editing", "Editing & culling"
        WEBSITE = "website", "Photographer website"
        BOOKING = "booking", "Bookings & calendar"
        CLIENT_ACCESS = "client_access", "Client access"
        TECHNICAL = "technical", "Technical issue"
        OTHER = "other", "Other"

    reference = models.CharField(max_length=16, unique=True, default=support_ticket_reference, editable=False)
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="support_tickets")
    requester_type = models.CharField(max_length=24, blank=True)
    category = models.CharField(max_length=32, choices=Category.choices)
    subject = models.CharField(max_length=180)
    description = models.TextField()
    related_url = models.URLField(blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.NORMAL)
    queue = models.ForeignKey(Department, on_delete=models.SET_NULL, related_name="support_tickets", null=True, blank=True)
    assignee = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, related_name="assigned_tickets", null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status", "priority", "created_at"), name="support_ticket_queue_idx"),
            models.Index(fields=("assignee", "status"), name="support_ticket_owner_idx"),
            models.Index(fields=("requester", "created_at"), name="support_ticket_req_idx"),
        ]

    def __str__(self):
        return f"{self.reference} — {self.subject}"


class SupportTicketComment(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="comments")
    author_employee = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, related_name="ticket_comments", null=True, blank=True)
    author_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="support_ticket_comments", null=True, blank=True)
    body = models.TextField()
    is_internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return f"Comment on {self.ticket.reference}"
