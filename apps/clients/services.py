from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Client, ClientActivity, ClientNote, Lead


@transaction.atomic
def create_client_note(*, client, content, actor):
    """Persist a validated note and its immutable audit event atomically.

    Workspace, client, actor and timestamp are deliberately derived by the
    server-side caller rather than accepted as independently writable fields.
    """
    locked_client = (
        Client.objects.select_for_update()
        .for_photographer(client.photographer)
        .get(pk=client.pk)
    )
    note = ClientNote(
        photographer=locked_client.photographer,
        client=locked_client,
        author=actor,
        content=content.strip(),
    )
    note.full_clean()
    note.save()
    ClientActivity.objects.create(
        photographer=locked_client.photographer,
        client=locked_client,
        actor=actor,
        event_type=ClientActivity.EventType.NOTE_ADDED,
        description="A client note was added.",
        metadata={"note_id": note.pk},
    )
    return note


class DuplicateClientError(ValidationError):
    """Raised when conversion would duplicate a workspace client identity."""


@transaction.atomic
def convert_lead_to_client(*, lead, actor):
    """Convert and audit a tenant-owned lead as one idempotent transaction."""
    locked_lead = (
        Lead.objects.select_for_update()
        .for_photographer(lead.photographer)
        .get(pk=lead.pk)
    )
    existing_conversion = Client.objects.filter(converted_lead=locked_lead).first()
    if existing_conversion:
        return existing_conversion, False

    email = locked_lead.email.strip()
    if email:
        duplicate = (
            Client.objects.select_for_update()
            .for_photographer(locked_lead.photographer)
            .filter(email__iexact=email)
            .first()
        )
        if duplicate:
            raise DuplicateClientError(
                "A client with this email address already exists. Open that client instead."
            )

    previous_status = locked_lead.status
    try:
        client, created = locked_lead.convert_to_client()
    except ValidationError as error:
        if "client with this email address already exists" in " ".join(error.messages):
            raise DuplicateClientError(error.messages) from error
        raise
    if created:
        ClientActivity.objects.create(
            photographer=locked_lead.photographer,
            actor=actor,
            lead=locked_lead,
            client=client,
            event_type=ClientActivity.EventType.LEAD_CONVERTED,
            description=(
                f"Lead stage changed from {Lead.Status(previous_status).label} to "
                f"{locked_lead.get_status_display()}."
            ),
            metadata={
                "from": previous_status,
                "to": locked_lead.status,
                "client_id": client.pk,
            },
        )
    lead.status = locked_lead.status
    return client, created
