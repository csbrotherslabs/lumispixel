"""Workspace-facing contract forms with tenant-scoped choices."""
from django import forms

from apps.clients.contracts import MERGE_FIELDS, unknown_merge_fields
from apps.clients.models import Contract, ContractTemplate
from apps.dashboard.contract_starters import CONTRACT_STARTER_CHOICES


class ContractTemplateForm(forms.ModelForm):
    start_from = forms.ChoiceField(
        choices=CONTRACT_STARTER_CHOICES,
        required=False,
        help_text="Choose a LumisPixel starter template or start with a blank contract.",
        widget=forms.Select(attrs={"data-contract-starter": ""}),
    )

    class Meta:
        model = ContractTemplate
        fields = ("name", "description", "category", "title", "content", "is_active")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "content": forms.Textarea(attrs={
                "rows": 16,
                "placeholder": "Start writing your contract terms here...",
            }),
        }

    def clean_content(self):
        content = self.cleaned_data["content"]
        unknown = unknown_merge_fields(content)
        if unknown:
            raise forms.ValidationError("Unsupported merge field(s): %s" % ", ".join("{{ %s }}" % item for item in unknown))
        return content


class ContractCustomizeForm(forms.ModelForm):
    class Meta:
        model = Contract
        fields = ("title", "content")
        widgets = {"content": forms.Textarea(attrs={"rows": 24})}


class ContractCreateForm(forms.Form):
    template = forms.ModelChoiceField(
        queryset=ContractTemplate.objects.none(),
        empty_label="Select a contract template",
        help_text="The draft will keep a snapshot of this template's current title and content.",
    )

    def __init__(self, *args, studio, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["template"].queryset = ContractTemplate.objects.filter(
            photographer=studio, is_active=True,
        ).order_by("name", "pk")
