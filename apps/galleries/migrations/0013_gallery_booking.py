from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0023_contract_photographer_signature"),
        ("galleries", "0012_galleryphoto_private_spaces_storage"),
    ]

    operations = [
        migrations.AddField(
            model_name="gallery",
            name="booking",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="galleries",
                to="clients.clientsession",
            ),
        ),
    ]
