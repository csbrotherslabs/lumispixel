from django.conf import settings
from django.db import models
from django.utils import timezone


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
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="roles",
        null=True,
        blank=True,
        help_text="Leave blank for company-wide roles such as Executive or Administrator.",
    )
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

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_profile",
    )
    employee_id = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=120, blank=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="employees",
        null=True,
        blank=True,
    )
    role = models.ForeignKey(
        InternalRole,
        on_delete=models.PROTECT,
        related_name="employees",
        null=True,
        blank=True,
    )
    manager = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="direct_reports",
        null=True,
        blank=True,
    )
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

    actor = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.SET_NULL,
        related_name="audit_events",
        null=True,
        blank=True,
    )
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
        indexes = [
            models.Index(fields=("category", "created_at"), name="internal_audit_cat_idx"),
            models.Index(fields=("actor", "created_at"), name="internal_audit_actor_idx"),
        ]

    def __str__(self):
        return f"{self.get_category_display()}: {self.summary}"
