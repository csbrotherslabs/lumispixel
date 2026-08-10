"""Workspace-facing contract forms with tenant-scoped choices."""
from django import forms

from apps.clients.models import ContractTemplate


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
