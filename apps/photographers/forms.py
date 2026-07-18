from zoneinfo import available_timezones

from django import forms
from django.db.models import Case, IntegerField, Value, When

from apps.accounts.models import PhotographerProfile, PhotographerSpecialty
from apps.clients.forms import COMMON_TIMEZONES, timezone_choices


class PhotographerOnboardingProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, label="First name")
    last_name = forms.CharField(max_length=150, label="Last name")

    class Meta:
        model = PhotographerProfile
        fields = [
            "display_name",
            "business_name",
            "profile_photo",
            "business_logo",
            "phone_number",
            "website",
            "country",
            "state",
            "city",
            "timezone",
        ]
        labels = {
            "display_name": "Display name",
            "business_name": "Business or studio name",
            "profile_photo": "Profile photo",
            "business_logo": "Business logo",
            "phone_number": "Phone number",
            "website": "Website",
            "timezone": "Time zone",
        }
        widgets = {
            "display_name": forms.TextInput(attrs={"class": "form-control", "autocomplete": "nickname"}),
            "business_name": forms.TextInput(attrs={"class": "form-control", "autocomplete": "organization"}),
            "profile_photo": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "business_logo": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "phone_number": forms.TextInput(attrs={"class": "form-control", "autocomplete": "tel"}),
            "website": forms.URLInput(attrs={"class": "form-control", "autocomplete": "url"}),
            "country": forms.TextInput(attrs={"class": "form-control", "autocomplete": "country-name"}),
            "state": forms.TextInput(attrs={"class": "form-control", "autocomplete": "address-level1"}),
            "city": forms.TextInput(attrs={"class": "form-control", "autocomplete": "address-level2"}),
            "timezone": forms.Select(attrs={"class": "form-control"}, choices=timezone_choices()),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["first_name"].widget.attrs.update({"class": "form-control", "autocomplete": "given-name"})
        self.fields["last_name"].widget.attrs.update({"class": "form-control", "autocomplete": "family-name"})
        for name in ("first_name", "last_name", "display_name", "country", "state", "city", "timezone"):
            self.fields[name].required = True
        if user and not self.is_bound:
            self.fields["first_name"].initial = user.first_name
            self.fields["last_name"].initial = user.last_name

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.user:
            self.user.first_name = self.cleaned_data["first_name"].strip()
            self.user.last_name = self.cleaned_data["last_name"].strip()
        if commit:
            if self.user:
                self.user.save(update_fields=["first_name", "last_name", "updated_at"])
            profile.save()
        return profile


class PhotographerSpecialtiesForm(forms.ModelForm):
    specialties = forms.ModelMultipleChoiceField(
        queryset=PhotographerSpecialty.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "lumis-onboarding__checkbox"}),
        required=False,
        label="Photography specialties",
    )

    class Meta:
        model = PhotographerProfile
        fields = ["specialties"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["specialties"].queryset = (
            PhotographerSpecialty.objects.filter(is_active=True)
            .annotate(
                _other_sort=Case(
                    When(slug="other", then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            )
            .order_by("_other_sort", "name")
        )


class PhotographerBusinessPreferencesForm(forms.ModelForm):
    class Meta:
        model = PhotographerProfile
        fields = [
            "business_type",
            "years_of_experience",
            "service_area",
            "willing_to_travel",
            "default_currency",
            "instagram_url",
            "facebook_url",
            "tiktok_url",
            "linkedin_url",
            "youtube_url",
        ]
        labels = {"business_type": "Business type", "years_of_experience": "Years of experience", "service_area": "Service area", "willing_to_travel": "Willing to travel", "default_currency": "Default currency", "instagram_url": "Instagram URL", "facebook_url": "Facebook URL", "tiktok_url": "TikTok URL", "linkedin_url": "LinkedIn URL", "youtube_url": "YouTube URL"}
        widgets = {
            "business_type": forms.Select(attrs={"class": "form-control"}),
            "years_of_experience": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "service_area": forms.TextInput(attrs={"class": "form-control"}),
            "willing_to_travel": forms.CheckboxInput(attrs={"class": "lumis-onboarding__checkbox"}),
            "default_currency": forms.TextInput(attrs={"class": "form-control", "maxlength": "3", "placeholder": "USD"}),
            "instagram_url": forms.URLInput(attrs={"class": "form-control"}),
            "facebook_url": forms.URLInput(attrs={"class": "form-control"}),
            "tiktok_url": forms.URLInput(attrs={"class": "form-control"}),
            "linkedin_url": forms.URLInput(attrs={"class": "form-control"}),
            "youtube_url": forms.URLInput(attrs={"class": "form-control"}),
        }

    def clean_default_currency(self):
        return self.cleaned_data["default_currency"].upper()


class PhotographerThemeForm(forms.ModelForm):
    class Meta:
        model = PhotographerProfile
        fields = ["website_theme"]
        widgets = {"website_theme": forms.RadioSelect(attrs={"class": "lumis-onboarding__theme-radio"})}
