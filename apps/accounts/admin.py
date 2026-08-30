from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django import forms

from .models import AdministrativeRegion, ClientProfile, Country, LocationDatasetImport, PhotographerProfile, PhotographerSpecialty, PhotographerWebsiteSection, User


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
        ("LumisPixel account", {"fields": ("primary_role", "last_active_workspace", "account_status", "email_verified", "email_verified_at", "onboarding_completed", "required_password_reset", "terms_accepted_at", "privacy_policy_accepted_at")} ),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")} ),
        ("Important dates", {"fields": ("last_login", "date_joined", "updated_at")} ),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "first_name", "last_name", "primary_role", "password1", "password2", "is_staff", "is_active")} ),)
    filter_horizontal = ("groups", "user_permissions")


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "city", "state", "country", "onboarding_completed", "marketing_emails", "created_at")
    list_filter = ("onboarding_completed", "marketing_emails", "country", "state")
    search_fields = ("user__email", "user__first_name", "user__last_name", "display_name", "city", "state", "country")


@admin.register(PhotographerProfile)
class PhotographerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "business_name", "business_type", "website_theme", "onboarding_completed", "public_profile_enabled")
    list_filter = ("business_type", "website_theme", "onboarding_completed", "willing_to_travel", "public_profile_enabled", "country", "state")
    search_fields = ("user__email", "user__first_name", "user__last_name", "display_name", "business_name", "city", "state", "country")
    prepopulated_fields = {"slug": ("display_name",)}
    filter_horizontal = ("specialties",)


@admin.register(PhotographerSpecialty)
class PhotographerSpecialtyAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "iso2", "iso3", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "iso2", "iso3")


@admin.register(AdministrativeRegion)
class AdministrativeRegionAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "code", "region_type", "is_active")
    list_filter = ("country", "region_type", "is_active")
    search_fields = ("name", "code", "country__name")


@admin.register(LocationDatasetImport)
class LocationDatasetImportAdmin(admin.ModelAdmin):
    list_display = ("source", "revision", "country_count", "region_count", "imported_at")
    readonly_fields = ("source", "revision", "country_count", "region_count", "imported_at")


@admin.register(PhotographerWebsiteSection)
class PhotographerWebsiteSectionAdmin(admin.ModelAdmin):
    list_display = ("photographer_website", "section_type", "layout_variant", "display_order", "is_enabled")
    list_filter = ("section_type", "is_enabled")
    search_fields = ("photographer_website__photographer_profile__business_name", "section_type", "layout_variant")
