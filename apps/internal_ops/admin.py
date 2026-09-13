from django.contrib import admin

from .models import ApprovalRequest, Department, EmployeeProfile, InternalAuditEvent, InternalRole, SupportTicket, SupportTicketAttachment, SupportTicketComment, SystemAlert


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "updated_at")
    search_fields = ("name", "code")
    list_filter = ("is_active",)


@admin.register(InternalRole)
class InternalRoleAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "is_executive", "is_active")
    search_fields = ("name", "code")
    list_filter = ("is_executive", "is_active", "department")


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "user", "title", "department", "role", "status")
    search_fields = ("employee_id", "user__email", "user__first_name", "user__last_name")
    list_filter = ("status", "department", "role")
    autocomplete_fields = ("user", "manager")


class SupportTicketCommentInline(admin.TabularInline):
    model = SupportTicketComment
    extra = 0
    readonly_fields = ("author_employee", "author_user", "body", "is_internal", "created_at")
    can_delete = False


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("reference", "subject", "requester", "status", "priority", "queue", "assignee", "updated_at")
    search_fields = ("reference", "subject", "requester__email", "requester__first_name", "requester__last_name")
    list_filter = ("status", "priority", "category", "queue", "created_at")
    autocomplete_fields = ("requester", "assignee", "queue")
    readonly_fields = ("reference", "requester_type", "created_at", "updated_at", "resolved_at")
    inlines = (SupportTicketCommentInline,)


@admin.register(SupportTicketAttachment)
class SupportTicketAttachmentAdmin(admin.ModelAdmin):
    list_display = ("original_name", "ticket", "is_internal", "size_bytes", "created_at")
    search_fields = ("original_name", "ticket__reference", "ticket__requester__email")
    list_filter = ("is_internal", "created_at")
    readonly_fields = ("ticket", "comment", "file", "original_name", "content_type", "size_bytes", "uploaded_by_user", "uploaded_by_employee", "is_internal", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ("reference", "kind", "risk_level", "status", "requester_user", "approver_department", "created_at")
    search_fields = ("reference", "title", "target_id", "requester_user__email")
    list_filter = ("status", "risk_level", "kind", "approver_department", "created_at")
    readonly_fields = (
        "reference", "kind", "risk_level", "status", "title", "reason", "target_type", "target_id",
        "proposed_changes", "requester", "requester_user", "approver_department", "reviewed_by",
        "reviewed_by_user", "reviewed_at", "decision_note", "executed_at", "created_at", "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SystemAlert)
class SystemAlertAdmin(admin.ModelAdmin):
    list_display = ("key", "component", "severity", "status", "last_seen_at")
    search_fields = ("key", "component", "title", "message")
    list_filter = ("severity", "status", "component")
    readonly_fields = ("key", "component", "severity", "status", "title", "message", "metadata", "first_seen_at", "last_seen_at", "acknowledged_at", "acknowledged_by", "resolved_at", "resolved_by")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(InternalAuditEvent)
class InternalAuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "category", "action", "actor", "summary")
    search_fields = ("action", "summary", "target_id", "actor__user__email")
    list_filter = ("category", "created_at")
    readonly_fields = ("actor", "category", "action", "target_type", "target_id", "summary", "reason", "metadata", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
