from django.contrib import admin

from .models import Department, EmployeeProfile, InternalAuditEvent, InternalRole


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


@admin.register(InternalAuditEvent)
class InternalAuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "category", "action", "actor", "summary")
    search_fields = ("action", "summary", "target_id", "actor__user__email")
    list_filter = ("category", "created_at")
    readonly_fields = (
        "actor",
        "category",
        "action",
        "target_type",
        "target_id",
        "summary",
        "reason",
        "metadata",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
