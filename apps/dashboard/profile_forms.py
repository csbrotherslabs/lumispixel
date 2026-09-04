from django import forms

from apps.accounts.models import User


class PhotographerPersonalProfileForm(forms.ModelForm):
    """Edit person-level identity without mixing in studio/business settings."""

    class Meta:
        model = User
        fields = ("first_name", "last_name")
        widgets = {
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name", "placeholder": "First name"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name", "placeholder": "Last name"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "lpw-profile-input"
