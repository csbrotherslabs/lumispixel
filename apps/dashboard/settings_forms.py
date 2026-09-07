from django import forms

from apps.accounts.models import PhotographerProfile


class WorkspaceBusinessSettingsForm(forms.ModelForm):
    """Business-wide settings that already belong to the photographer/studio profile."""

    class Meta:
        model = PhotographerProfile
        fields = [
            "business_name",
            "business_logo",
            "phone_number",
            "website",
            "city",
            "state",
            "country",
            "timezone",
            "default_currency",
        ]
        widgets = {
            "business_name": forms.TextInput(attrs={"autocomplete": "organization"}),
            "phone_number": forms.TextInput(attrs={"autocomplete": "tel"}),
            "website": forms.URLInput(attrs={"autocomplete": "url", "placeholder": "https://"}),
            "city": forms.TextInput(attrs={"autocomplete": "address-level2"}),
            "state": forms.TextInput(attrs={"autocomplete": "address-level1"}),
            "country": forms.TextInput(attrs={"autocomplete": "country-name"}),
            "timezone": forms.TextInput(attrs={"placeholder": "America/Chicago", "autocomplete": "off"}),
            "default_currency": forms.TextInput(attrs={"maxlength": "3", "placeholder": "USD", "autocomplete": "off"}),
        }

    def clean_default_currency(self):
        value = (self.cleaned_data.get("default_currency") or "").strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise forms.ValidationError("Enter a three-letter currency code, such as USD.")
        return value

    def clean_timezone(self):
        value = (self.cleaned_data.get("timezone") or "").strip()
        if not value:
            raise forms.ValidationError("Enter the timezone used by your studio.")
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(value)
        except Exception as exc:
            raise forms.ValidationError("Enter a valid IANA timezone, such as America/Chicago.") from exc
        return value
