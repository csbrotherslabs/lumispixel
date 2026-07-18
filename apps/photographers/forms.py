from zoneinfo import available_timezones

from django import forms
from django.db.models import Case, IntegerField, Value, When

from apps.accounts.models import PhotographerProfile, PhotographerSpecialty, PhotographerWebsiteProfile, PhotographerWebsiteProject
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
            "default_currency",
            "travel_radius",
            "willing_to_travel",
            "destination_photographer",
            "available_nationally",
            "available_internationally",
            "instagram_url",
            "facebook_url",
            "tiktok_url",
            "linkedin_url",
            "youtube_url",
        ]
        labels = {
            "business_type": "Business type",
            "years_of_experience": "Years of experience",
            "default_currency": "Default currency",
            "travel_radius": "Travel radius",
            "willing_to_travel": "Willing to travel",
            "destination_photographer": "Destination photographer",
            "available_nationally": "Available nationally",
            "available_internationally": "Available internationally",
            "instagram_url": "Instagram URL",
            "facebook_url": "Facebook URL",
            "tiktok_url": "TikTok URL",
            "linkedin_url": "LinkedIn URL",
            "youtube_url": "YouTube URL",
        }
        help_texts = {
            "travel_radius": "Choose the local radius you routinely serve when traveling.",
            "destination_photographer": "Select this if you accept assignments that require travel outside your normal service area.",
            "available_nationally": "Available for assignments throughout your home country.",
            "available_internationally": "Available for assignments outside your home country.",
        }
        widgets = {
            "business_type": forms.Select(attrs={"class": "form-control"}),
            "years_of_experience": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "default_currency": forms.TextInput(attrs={"class": "form-control", "maxlength": "3", "placeholder": "USD"}),
            "travel_radius": forms.Select(attrs={"class": "form-control", "data-travel-dependent": "true"}),
            "willing_to_travel": forms.CheckboxInput(attrs={"class": "lumis-onboarding__checkbox", "data-travel-toggle": "true"}),
            "destination_photographer": forms.CheckboxInput(attrs={"class": "lumis-onboarding__checkbox", "data-travel-dependent": "true"}),
            "available_nationally": forms.CheckboxInput(attrs={"class": "lumis-onboarding__checkbox", "data-travel-dependent": "true"}),
            "available_internationally": forms.CheckboxInput(attrs={"class": "lumis-onboarding__checkbox", "data-travel-dependent": "true"}),
            "instagram_url": forms.URLInput(attrs={"class": "form-control"}),
            "facebook_url": forms.URLInput(attrs={"class": "form-control"}),
            "tiktok_url": forms.URLInput(attrs={"class": "form-control"}),
            "linkedin_url": forms.URLInput(attrs={"class": "form-control"}),
            "youtube_url": forms.URLInput(attrs={"class": "form-control"}),
        }

    def clean_default_currency(self):
        return self.cleaned_data["default_currency"].upper()

    def clean(self):
        cleaned_data = super().clean()
        willing = cleaned_data.get("willing_to_travel")
        destination = cleaned_data.get("destination_photographer")
        nationally = cleaned_data.get("available_nationally")
        internationally = cleaned_data.get("available_internationally")
        radius = cleaned_data.get("travel_radius")

        if destination or nationally or internationally:
            willing = True
            cleaned_data["willing_to_travel"] = True

        if not willing:
            cleaned_data["travel_radius"] = None
            cleaned_data["destination_photographer"] = False
            cleaned_data["available_nationally"] = False
            cleaned_data["available_internationally"] = False
        elif not radius and not nationally and not internationally:
            self.add_error("travel_radius", "Select a travel radius or indicate national/international availability.")

        return cleaned_data


class PhotographerThemeForm(forms.ModelForm):
    class Meta:
        model = PhotographerProfile
        fields = ["website_theme"]
        widgets = {"website_theme": forms.RadioSelect(attrs={"class": "lumis-onboarding__theme-radio"})}

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024

THEME_FIELD_CONFIG = {
    PhotographerProfile.WebsiteTheme.BASIC: {"required": [], "optional": []},
    PhotographerProfile.WebsiteTheme.ELEGANT: {"required": ["hero_heading", "hero_subheading", "about_heading", "about_text", "featured_gallery_title", "booking_call_to_action"], "optional": ["testimonial_quote", "testimonial_name"]},
    PhotographerProfile.WebsiteTheme.MODERN_STUDIO: {"required": ["hero_heading", "studio_intro", "services_intro", "consultation_call_to_action"], "optional": ["client_list", "featured_project_title", "featured_project_description"]},
    PhotographerProfile.WebsiteTheme.CINEMATIC: {"required": ["hero_media_type", "hero_heading", "hero_subheading", "story_heading", "story_text", "contact_call_to_action"], "optional": ["hero_video", "featured_video_url"]},
    PhotographerProfile.WebsiteTheme.PORTFOLIO_EDITORIAL: {"required": ["editorial_heading", "artist_statement", "project_section_heading", "contact_statement"], "optional": []},
    PhotographerProfile.WebsiteTheme.SPORTS_EVENTS: {"required": ["hero_heading", "hero_subheading", "find_photos_heading", "recent_events_heading", "booking_call_to_action"], "optional": ["highlight_video", "featured_event_title", "featured_event_description"]},
}

class PhotographerWebsiteThemeForm(forms.ModelForm):
    action = forms.CharField(required=False)
    hero_image = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={"class":"form-control","accept":"image/jpeg,image/png,image/webp,image/gif"}))
    field_names = sorted({f for cfg in THEME_FIELD_CONFIG.values() for f in cfg["required"] + cfg["optional"]})
    hero_media_type = forms.ChoiceField(choices=(("image","Image"),("video","Video")), required=False, widget=forms.Select(attrs={"class":"form-control"}))
    class Meta:
        model = PhotographerProfile
        fields = ["website_theme"]
        widgets = {"website_theme": forms.RadioSelect(attrs={"class":"lumis-onboarding__theme-radio"})}

    def __init__(self, *args, website_profile=None, draft=False, **kwargs):
        self.website_profile = website_profile
        self.draft = draft
        super().__init__(*args, **kwargs)
        content = (website_profile.theme_content if website_profile else {}) or {}
        if not self.is_bound:
            for name in self.field_names:
                self.fields[name].initial = content.get(name, "")
            if website_profile and website_profile.hero_image:
                self.fields["hero_image"].help_text = f"Current image: {website_profile.hero_image.name}"

    def clean_hero_image(self):
        image = self.cleaned_data.get("hero_image")
        if image:
            if image.content_type not in IMAGE_TYPES:
                raise forms.ValidationError("Upload a JPG, PNG, GIF, or WebP image.")
            if image.size > MAX_IMAGE_SIZE:
                raise forms.ValidationError("Image uploads must be 5 MB or smaller.")
        return image

    def clean(self):
        cleaned = super().clean()
        theme = cleaned.get("website_theme")
        if theme not in THEME_FIELD_CONFIG:
            return cleaned
        required = THEME_FIELD_CONFIG[theme]["required"]
        if not self.draft:
            for name in required:
                if not str(cleaned.get(name) or "").strip():
                    self.add_error(name, "This field is required for the selected theme.")
        for name in ("hero_video", "featured_video_url", "highlight_video"):
            value = cleaned.get(name)
            if value and not (value.startswith("https://") or value.startswith("http://")):
                self.add_error(name, "Enter a valid video URL starting with http:// or https://.")
        return cleaned

    def save_theme(self):
        profile = self.save(commit=False)
        website, _ = PhotographerWebsiteProfile.objects.get_or_create(photographer_profile=profile)
        allowed = set(THEME_FIELD_CONFIG[profile.website_theme]["required"] + THEME_FIELD_CONFIG[profile.website_theme]["optional"])
        content = dict(website.theme_content or {})
        for name in allowed:
            content[name] = self.cleaned_data.get(name, "")
        website.theme_content = content
        if self.cleaned_data.get("hero_image"):
            website.hero_image = self.cleaned_data["hero_image"]
        profile.save()
        website.save()
        return profile, website


for _theme_field_name in PhotographerWebsiteThemeForm.field_names:
    if _theme_field_name == "hero_media_type":
        continue
    _widget = forms.Textarea(attrs={"class":"form-control","rows":3}) if any(part in _theme_field_name for part in ("text", "intro", "statement", "description", "list")) else forms.TextInput(attrs={"class":"form-control"})
    PhotographerWebsiteThemeForm.base_fields[_theme_field_name] = forms.CharField(required=False, widget=_widget)
