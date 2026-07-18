from zoneinfo import available_timezones

from django import forms

from apps.accounts.models import ClientProfile


COMMON_TIMEZONES = [
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Phoenix",
    "America/Anchorage",
    "Pacific/Honolulu",
    "UTC",
]


def timezone_choices():
    zones = sorted(available_timezones())
    preferred = [(zone, zone.replace("_", " ")) for zone in COMMON_TIMEZONES if zone in zones]
    remaining = [(zone, zone.replace("_", " ")) for zone in zones if zone not in COMMON_TIMEZONES]
    return [("", "Select a time zone")] + preferred + remaining


class ClientOnboardingProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, label="First name")
    last_name = forms.CharField(max_length=150, label="Last name")

    class Meta:
        model = ClientProfile
        fields = [
            "profile_photo",
            "display_name",
            "country",
            "state",
            "city",
            "timezone",
            "marketing_emails",
        ]
        labels = {
            "profile_photo": "Profile photo (optional)",
            "display_name": "Display name (optional)",
            "timezone": "Time zone",
            "marketing_emails": "Send me marketing emails about LumisPixel updates and offers",
        }
        widgets = {
            "profile_photo": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "display_name": forms.TextInput(attrs={"class": "form-control", "autocomplete": "nickname"}),
            "country": forms.TextInput(attrs={"class": "form-control", "autocomplete": "country-name"}),
            "state": forms.TextInput(attrs={"class": "form-control", "autocomplete": "address-level1"}),
            "city": forms.TextInput(attrs={"class": "form-control", "autocomplete": "address-level2"}),
            "timezone": forms.Select(attrs={"class": "form-control"}, choices=timezone_choices()),
            "marketing_emails": forms.CheckboxInput(attrs={"class": "lumis-onboarding__checkbox"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["first_name"].widget.attrs.update({"class": "form-control", "autocomplete": "given-name"})
        self.fields["last_name"].widget.attrs.update({"class": "form-control", "autocomplete": "family-name"})
        for name in ("first_name", "last_name", "country", "state", "city", "timezone"):
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
