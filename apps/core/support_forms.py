from django import forms

from apps.internal_ops.models import SupportTicket


class SupportTicketIntakeForm(forms.ModelForm):
    category = forms.ChoiceField(
        choices=[("", "Choose an issue category")] + list(SupportTicket.Category.choices),
        widget=forms.Select(
            attrs={
                "class": "hc-field hc-select",
                "aria-describedby": "category-help",
            }
        ),
        error_messages={"required": "Choose the category that best matches your issue."},
    )

    class Meta:
        model = SupportTicket
        fields = ("category", "subject", "description", "related_url")
        widgets = {
            "subject": forms.TextInput(
                attrs={
                    "class": "hc-field",
                    "placeholder": "Example: Client cannot open wedding gallery",
                    "autocomplete": "off",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "hc-field",
                    "rows": 7,
                    "placeholder": "Tell us what happened, what you expected to happen, and any troubleshooting steps you already tried.",
                }
            ),
            "related_url": forms.URLInput(
                attrs={
                    "class": "hc-field",
                    "placeholder": "https://lumispixel.com/...",
                    "inputmode": "url",
                }
            ),
        }
        labels = {"related_url": "Related LumisPixel page"}

    def clean_category(self):
        category = self.cleaned_data.get("category")
        valid_categories = {value for value, _ in SupportTicket.Category.choices}
        if category not in valid_categories:
            raise forms.ValidationError("Choose a valid issue category.")
        return category
