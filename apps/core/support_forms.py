from django import forms

from apps.internal_ops.models import SupportTicket


class SupportTicketIntakeForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ("category", "subject", "description", "related_url")
        widgets = {
            "category": forms.Select(attrs={"class": "hc-field"}),
            "subject": forms.TextInput(attrs={"class": "hc-field", "placeholder": "Briefly describe what you need help with"}),
            "description": forms.Textarea(attrs={"class": "hc-field", "rows": 7, "placeholder": "Tell us what happened, what you expected, and any steps you already tried."}),
            "related_url": forms.URLInput(attrs={"class": "hc-field", "placeholder": "Optional: link to the affected LumisPixel page"}),
        }
        labels = {"related_url": "Related LumisPixel page"}
