import hashlib
from django.db import migrations
from django.utils import timezone


def confirm_existing(apps, schema_editor):
    Contract = apps.get_model("clients", "Contract")
    Session = apps.get_model("clients", "ClientSession")
    Activity = apps.get_model("clients", "ClientActivity")
    db = schema_editor.connection.alias
    contracts = Contract.objects.using(db).filter(
        status="signed", booking__status="tentative", booking__event_kind="booking",
        signature__isnull=False, photographer_signature__isnull=False,
    ).select_related("signature", "photographer_signature").order_by("signed_at", "pk")
    for contract in contracts.iterator():
        client = contract.signature
        photographer = contract.photographer_signature
        digest = hashlib.sha256(contract.rendered_content.encode("utf-8")).hexdigest()
        if not (contract.rendered_content and client.consent_accepted and photographer.consent_accepted
                and client.content_hash == photographer.content_hash == digest
                and client.client_id == contract.client_id
                and client.photographer_id == photographer.photographer_id == contract.photographer_id):
            continue
        confirmed_at = contract.signed_at or client.signed_at
        updated = Session.objects.using(db).filter(
            pk=contract.booking_id, photographer_id=contract.photographer_id,
            client_id=contract.client_id, status="tentative", event_kind="booking",
        ).update(status="confirmed", confirmed_at=confirmed_at, updated_at=timezone.now())
        if updated:
            Activity.objects.using(db).create(
                photographer_id=contract.photographer_id, client_id=contract.client_id,
                booking_id=contract.booking_id, event_type="booking_updated",
                description="Booking automatically confirmed from an existing fully signed agreement.",
                metadata={"contract_id": contract.pk, "before": "tentative", "after": "confirmed"},
            )


class Migration(migrations.Migration):
    dependencies = [("clients", "0026_booking_payment_terms")]
    operations = [migrations.RunPython(confirm_existing, migrations.RunPython.noop)]
