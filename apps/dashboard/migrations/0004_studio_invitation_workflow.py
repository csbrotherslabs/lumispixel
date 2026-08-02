from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("dashboard", "0003_studiomembership"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name="studiomembership", name="invitation_first_name", field=models.CharField(blank=True, max_length=150)),
        migrations.AddField(model_name="studiomembership", name="invitation_last_name", field=models.CharField(blank=True, max_length=150)),
        migrations.AddField(model_name="studiomembership", name="invitation_phone", field=models.CharField(blank=True, max_length=30)),
        migrations.AddField(model_name="studiomembership", name="invitation_message", field=models.TextField(blank=True)),
        migrations.AddField(model_name="studiomembership", name="invitation_token_digest", field=models.CharField(blank=True, editable=False, max_length=64)),
        migrations.AddField(model_name="studiomembership", name="invitation_sent_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="studiomembership", name="invited_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="studio_invitations_sent", to=settings.AUTH_USER_MODEL)),
        migrations.CreateModel(name="StudioInvitationEvent", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("action", models.CharField(choices=[("sent", "Sent"), ("resent", "Resent"), ("revoked", "Revoked"), ("accepted", "Accepted"), ("declined", "Declined")], max_length=12)),
            ("occurred_at", models.DateTimeField(auto_now_add=True)),
            ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="studio_invitation_events", to=settings.AUTH_USER_MODEL)),
            ("membership", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="invitation_events", to="dashboard.studiomembership")),
        ], options={"ordering": ["-occurred_at"]}),
        migrations.AddConstraint(model_name="studiomembership", constraint=models.UniqueConstraint(condition=models.Q(("status", "invited")), fields=("studio", "invitation_email"), name="unique_pending_studio_invitation_email")),
    ]
