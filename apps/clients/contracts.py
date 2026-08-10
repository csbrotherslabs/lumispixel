"""Canonical creation operations for booking contracts."""
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Contract, ContractEvent, ContractTemplate


@transaction.atomic
def create_contract_from_template(*, booking, template, actor):
    """Create a draft snapshot without retaining live template content."""
    if booking.photographer_id != template.photographer_id:
        raise ValidationError({"template": "The template and booking must belong to the same photographer."})
    contract = Contract(
        photographer=booking.photographer,
        booking=booking,
        client=booking.client,
        template=template,
        title=template.title,
        content=template.content,
        version=template.version,
        status=Contract.Status.DRAFT,
        created_by=actor,
    )
    contract.full_clean()
    contract.save()
    ContractEvent.objects.create(
        contract=contract,
        actor=actor,
        event_type=ContractEvent.EventType.CREATED,
        metadata={"template_id": template.pk, "template_version": template.version},
    )
    return contract
