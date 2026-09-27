from zoneinfo import available_timezones

from django import forms
from django.urls import reverse

from apps.accounts.models import AdministrativeRegion, ClientProfile, Country
from .models import Client, ClientTask, Lead


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
    country_record = forms.ModelChoiceField(
        queryset=Country.objects.none(),
        label="Country",
        empty_label="Select a country",
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "autocomplete": "country-name",
                "data-location-country": "",
            }
        ),
    )
    administrative_region = forms.ModelChoiceField(
        queryset=AdministrativeRegion.objects.none(),
        label="State or region",
        required=False,
        empty_label="Select a state, province, or region",
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "autocomplete": "address-level1",
                "data-location-region": "",
            }
        ),
    )

    class Meta:
        model = ClientProfile
        fields = [
            "profile_photo",
            "display_name",
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
            "city": forms.TextInput(attrs={"class": "form-control", "autocomplete": "address-level2"}),
            "timezone": forms.Select(attrs={"class": "form-control"}, choices=timezone_choices()),
            "marketing_emails": forms.CheckboxInput(attrs={"class": "lumis-onboarding__checkbox"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["first_name"].widget.attrs.update({"class": "form-control", "autocomplete": "given-name"})
        self.fields["last_name"].widget.attrs.update({"class": "form-control", "autocomplete": "family-name"})

        self.fields["country_record"].queryset = Country.objects.filter(is_active=True).order_by("name")
        self.fields["country_record"].widget.attrs["data-regions-url"] = reverse("api:administrative-regions")

        selected_country_id = self.data.get("country_record") if self.is_bound else None
        selected_country = None
        if selected_country_id and str(selected_country_id).isdigit():
            selected_country = self.fields["country_record"].queryset.filter(pk=selected_country_id).first()
        elif not self.is_bound and self.instance and self.instance.country:
            selected_country = self.fields["country_record"].queryset.filter(name__iexact=self.instance.country.strip()).first()
            if selected_country:
                self.fields["country_record"].initial = selected_country

        regions = AdministrativeRegion.objects.none()
        if selected_country:
            regions = AdministrativeRegion.objects.filter(country=selected_country, is_active=True).order_by("name")
        self.fields["administrative_region"].queryset = regions
        self.fields["administrative_region"].required = regions.exists()

        if not self.is_bound and selected_country and self.instance and self.instance.state:
            selected_region = regions.filter(name__iexact=self.instance.state.strip()).first()
            if selected_region:
                self.fields["administrative_region"].initial = selected_region

        for name in ("first_name", "last_name", "country_record", "city", "timezone"):
            self.fields[name].required = True
        if user and not self.is_bound:
            self.fields["first_name"].initial = user.first_name
            self.fields["last_name"].initial = user.last_name

    def save(self, commit=True):
        profile = super().save(commit=False)
        country = self.cleaned_data["country_record"]
        region = self.cleaned_data.get("administrative_region")
        profile.country = country.name
        profile.state = region.name if region else ""
        if self.user:
            self.user.first_name = self.cleaned_data["first_name"].strip()
            self.user.last_name = self.cleaned_data["last_name"].strip()
        if commit:
            if self.user:
                self.user.save(update_fields=["first_name", "last_name", "updated_at"])
            profile.save()
        return profile


class LeadForm(forms.ModelForm):
    lead_source = forms.ChoiceField(
        required=False,
        choices=(
            ("", "Select a lead source"),
            ("referral", "Referral"),
            ("website", "Website"),
            ("social", "Social media"),
            ("event", "Event"),
            ("other", "Other"),
        ),
    )

    class Meta:
        model = Lead
        fields = ("first_name", "last_name", "email", "phone", "event_type", "event_date", "lead_source", "estimated_value", "status", "next_follow_up", "notes")
        labels = {"estimated_value": "Estimated value"}
        widgets = {
            "event_date": forms.DateInput(attrs={"type": "date"}),
            "next_follow_up": forms.DateInput(attrs={"type": "date"}),
            "estimated_value": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "notes": forms.Textarea(attrs={"rows": 7}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            "first_name": "e.g. Avery",
            "last_name": "e.g. Morgan",
            "email": "avery@example.com",
            "phone": "+1 (555) 123-4567",
            "event_type": "e.g. Wedding, portrait, or event",
            "estimated_value": "0.00",
            "notes": "Add inquiry details, preferences, follow-up context, or anything your team should know…",
        }
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", "form-control")
            if name in placeholders:
                field.widget.attrs.setdefault("placeholder", placeholders[name])
            field.widget.attrs.setdefault("autocomplete", "off")
        self.fields["lead_source"].widget.attrs["class"] = "form-select"
        self.fields["status"].widget.attrs["class"] = "form-select"
        self.fields["status"].required = False
        self.fields["status"].initial = self.instance.status or Lead.Status.NEW
        self.fields["first_name"].widget.attrs["autocomplete"] = "given-name"
        self.fields["last_name"].widget.attrs["autocomplete"] = "family-name"
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["phone"].widget.attrs["autocomplete"] = "tel"

    def clean(self):
        data = super().clean()
        data["status"] = data.get("status") or Lead.Status.NEW
        if data["status"] == Lead.Status.LOST:
            self.add_error("status", "Use Mark lost so a loss reason can be recorded.")
        if (
            data.get("status") == Lead.Status.BOOKED
            and data.get("email")
            and self.instance.photographer_id
            and Client.objects.for_photographer(self.instance.photographer).filter(
                email__iexact=data["email"].strip()
            ).exclude(converted_lead=self.instance).exists()
        ):
            self.add_error(
                "email",
                "A client with this email address already exists. Open that client instead.",
            )
        if not data.get("email") and not data.get("phone"):
            raise forms.ValidationError("Provide an email address or phone number.")
        return data


class CrmClientForm(forms.ModelForm):
    city = forms.CharField(required=False, max_length=100)
    state_province = forms.CharField(required=False, max_length=100, label="State or province")
    postal_code = forms.CharField(required=False, max_length=20)
    country = forms.CharField(required=False, max_length=100)
    client_type = forms.ChoiceField(required=False, choices=(("", "Select a client type"), *Client.ClientType.choices))
    lead_source = forms.ChoiceField(required=False, choices=(("", "Select a lead source"), ("referral", "Referral"), ("website", "Website"), ("social", "Social media"), ("event", "Event"), ("other", "Other")))
    preferred_contact_method = forms.ChoiceField(required=False, choices=(("", "Select a contact method"), *Client.ContactMethod.choices))
    tags_input = forms.CharField(required=False, label="Tags")
    notes = forms.CharField(required=False, max_length=2000, widget=forms.Textarea(attrs={"rows": 7}))

    class Meta:
        model = Client
        fields = ("first_name", "last_name", "email", "phone", "company", "address", "birthday", "status", "client_type", "preferred_contact_method", "profile_photo")
        labels = {"address": "Street address"}
        widgets = {"birthday": forms.DateInput(attrs={"type": "date"}), "address": forms.TextInput()}

    def __init__(self, *args, photographer=None, **kwargs):
        self.photographer = photographer
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial["lead_source"] = self.instance.lead_source
            self.initial["tags_input"] = ", ".join(self.instance.tags or [])
            address_parts = (self.instance.address or "").splitlines()
            self.initial["address"] = address_parts[0] if address_parts else ""
            for name, value in zip(("city", "state_province", "postal_code", "country"), address_parts[1:]):
                self.initial[name] = value
        placeholders = {"first_name": "e.g. Avery", "last_name": "e.g. Morgan", "email": "avery@example.com", "phone": "+1 (555) 123-4567", "company": "Studio or company name", "address": "Street and number", "city": "City", "state_province": "State or province", "postal_code": "Postal code", "country": "Country", "tags_input": "Type a tag and press Enter", "notes": "Add preferences, important dates, project context, or anything your team should know…"}
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", "form-control")
            if name in placeholders:
                field.widget.attrs.setdefault("placeholder", placeholders[name])
            field.widget.attrs.setdefault("autocomplete", "off")
        for name in ("status", "client_type", "lead_source", "preferred_contact_method"):
            self.fields[name].widget.attrs["class"] = "form-select"
        self.fields["first_name"].widget.attrs["autocomplete"] = "given-name"
        self.fields["last_name"].widget.attrs["autocomplete"] = "family-name"
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["phone"].widget.attrs["autocomplete"] = "tel"
        self.fields["profile_photo"].widget.attrs.update({
            "accept": "image/png,image/jpeg,image/webp",
            "data-photo-input": "",
        })

    def clean_tags_input(self):
        tags = [tag.strip() for tag in self.cleaned_data.get("tags_input", "").split(",") if tag.strip()]
        return list(dict.fromkeys(tags))[:20]

    def clean(self):
        data = super().clean()
        if not data.get("email") and not data.get("phone"):
            raise forms.ValidationError("Provide an email address or phone number.")
        email = (data.get("email") or "").strip()
        photographer = self.photographer or getattr(self.instance, "photographer", None)
        if email and photographer:
            duplicates = Client.objects.for_photographer(photographer).filter(email__iexact=email)
            if self.instance.pk:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                self.add_error(
                    "email",
                    "A client with this email address already exists. Open that client instead.",
                )
        return data

    def save(self, commit=True):
        client = super().save(commit=False)
        parts = [self.cleaned_data.get(name, "").strip() for name in ("address", "city", "state_province", "postal_code", "country")]
        client.address = "\n".join(part for part in parts if part)
        client.lead_source = self.cleaned_data.get("lead_source", "")
        client.tags = self.cleaned_data.get("tags_input", [])
        if commit:
            client.save()
        return client


class ClientTaskForm(forms.ModelForm):
    class Meta:
        model = ClientTask
        fields = ("title", "due_date", "priority", "lead", "client")
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, photographer, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["lead"].queryset = Lead.objects.for_photographer(photographer)
        self.fields["client"].queryset = Client.objects.for_photographer(photographer)

    def clean(self):
        data = super().clean()
        if bool(data.get("lead")) == bool(data.get("client")):
            raise forms.ValidationError("Choose exactly one lead or client.")
        return data