from django.db import migrations, models


def backfill_confirmation_dates(apps, schema_editor):
    session = apps.get_model("clients", "ClientSession")
    session.objects.filter(status__in=("confirmed", "completed"), confirmed_at__isnull=True).update(
        confirmed_at=models.F("created_at")
    )


class Migration(migrations.Migration):
    dependencies = [("clients", "0010_invoicecredit_expires_at_invoicecredit_internal_note_and_more")]
    operations = [
        migrations.AddField(
            model_name="clientsession",
            name="confirmed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_confirmation_dates, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name="clientsession",
            index=models.Index(fields=["photographer", "status", "confirmed_at"], name="session_owner_confirmed"),
        ),
    ]
