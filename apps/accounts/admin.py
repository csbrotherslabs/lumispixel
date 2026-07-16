from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django import forms

from .models import ClientProfile, PhotographerProfile, PhotographerSpecialty, User


class UserCreationForm(forms.ModelForm):
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Password confirmation", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "primary_role")

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField()

    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    model = User
    list_display = ("email", "first_name", "last_name", "primary_role", "account_status", "email_verified", "is_staff", "is_active")
    list_filter = ("primary_role", "account_status", "email_verified", "is_staff", "is_active", "last_active_workspace", "groups")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)
    readonly_fields = ("last_login", "date_joined", "updated_at", "email_verified_at")
    fieldsets = (
        (None, {"fields": ("email", "password")} ),
        ("Personal info", {"fields": ("first_name", "last_name")} ),
        ("LumiPixel account", {"fields": ("primary_role", "last_active_workspace", "account_status", "email_verified", "email_verified_at", "onboarding_completed", "required_password_reset", "terms_accepted_at", "privacy_policy_accepted_at")} ),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")} ),
        ("Important dates", {"fields": ("last_login", "date_joined", "updated_at")} ),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "first_name", "last_name", "primary_role", "password1", "password2", "is_staff", "is_active")} ),)
    filter_horizontal = ("groups", "user_permissions")


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "city", "state", "marketplace_enabled", "created_at")
    list_filter = ("marketplace_enabled", "state")
    search_fields = ("user__email", "user__first_name", "user__last_name", "city", "state")


@admin.register(PhotographerProfile)
class PhotographerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "business_name", "verification_status", "onboarding_completed", "accepts_marketplace_requests", "public_profile_enabled", "payout_setup_completed")
    list_filter = ("verification_status", "onboarding_completed", "accepts_marketplace_requests", "public_profile_enabled", "payout_setup_completed", "state")
    search_fields = ("user__email", "display_name", "business_name", "city", "state")
    prepopulated_fields = {"slug": ("display_name",)}
    filter_horizontal = ()


@admin.register(PhotographerSpecialty)
class PhotographerSpecialtyAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
