from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("LumisPixel fields", {"fields": ("role", "is_email_verified", "created_at", "updated_at")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("LumisPixel fields", {"fields": ("email", "role", "is_email_verified")}),
    )
    list_display = ("username", "email", "role", "is_email_verified", "is_staff", "is_active")
    list_filter = UserAdmin.list_filter + ("role", "is_email_verified")
    readonly_fields = ("created_at", "updated_at")
