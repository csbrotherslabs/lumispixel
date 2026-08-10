from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("clients", "0018_contracttemplate_contract_contractevent_and_more")]

    operations = [
        migrations.AddField(model_name="contract", name="rendered_content", field=models.TextField(blank=True)),
        migrations.AddField(model_name="contract", name="review_token_digest", field=models.CharField(blank=True, db_index=True, editable=False, max_length=64)),
        migrations.AddField(model_name="contract", name="review_token_expires_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="contract", name="review_token_revoked_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="contract", name="sent_to_email", field=models.EmailField(blank=True, max_length=254)),
        migrations.AddField(model_name="contract", name="send_count", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="contract", name="last_sent_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AlterField(model_name="contractevent", name="event_type", field=models.CharField(choices=[("created", "Created"), ("sent", "Sent"), ("resent", "Resent"), ("viewed", "Viewed")], max_length=24)),
    ]
