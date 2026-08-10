"""Canonical, tenant-safe operations for booking contracts and merge fields."""
import re

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import formats, timezone

from .models import Contract, ContractEvent, ContractTemplate


MERGE_FIELDS = {
    "client.first_name": "Client first name",
    "client.last_name": "Client last name",
    "client.full_name": "Client full name",
    "client.email": "Client email",
    "booking.service": "Booking service/title",
    "booking.date": "Booking date",
    "booking.start_time": "Booking start time",
    "booking.location": "Booking location",
    "booking.value": "Booking value",
    "workspace.name": "Workspace/business name",
    "photographer.name": "Photographer/studio name",
}
MERGE_PATTERN = re.compile(r"{{\s*([a-z][a-z0-9_.]*)\s*}}")


def unknown_merge_fields(content):
    """Return unsupported tokens without interpreting template content."""
    return sorted({field for field in MERGE_PATTERN.findall(content or "") if field not in MERGE_FIELDS})


def merge_context(booking):
    """Build values exclusively from the contract booking's persisted tenant data."""
    local_start = timezone.localtime(booking.starts_at)
    studio = booking.photographer
    owner = studio.user
    studio_name = studio.business_name or studio.display_name or owner.full_name or owner.email
    return {
        "client.first_name": booking.client.first_name,
        "client.last_name": booking.client.last_name,
        "client.full_name": str(booking.client),
        "client.email": booking.client.email,
        "booking.service": booking.session_type,
        "booking.date": formats.date_format(local_start, "DATE_FORMAT"),
        "booking.start_time": formats.time_format(local_start, "TIME_FORMAT"),
        "booking.location": booking.location,
        "booking.value": formats.number_format(booking.booking_value, decimal_pos=2),
        "workspace.name": studio_name,
        "photographer.name": studio_name,
    }


def render_merge_fields(content, booking):
    """Resolve known fields; retain unknown tokens visibly and harmlessly."""
    values = merge_context(booking)
    return MERGE_PATTERN.sub(lambda match: str(values.get(match.group(1), match.group(0))), content or "")


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
        content=render_merge_fields(template.content, booking),
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
