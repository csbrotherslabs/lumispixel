from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AutomationRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("description", models.CharField(blank=True, max_length=500)),
                ("trigger", models.CharField(choices=[("booking_confirmed", "Booking confirmed"), ("contract_signed", "Contract signed"), ("invoice_due", "Invoice due"), ("payment_received", "Payment received"), ("shoot_completed", "Shoot completed"), ("gallery_published", "Gallery published"), ("gallery_expiring", "Gallery nearing expiration")], max_length=40)),
                ("action", models.CharField(choices=[("send_contract", "Send contract"), ("prepare_invoice", "Prepare invoice"), ("send_invoice_reminder", "Send invoice reminder"), ("complete_financial_workflow", "Complete financial workflow"), ("create_gallery_task", "Create gallery task"), ("notify_gallery_client", "Notify gallery client"), ("send_gallery_expiration_reminder", "Send gallery expiration reminder")], max_length=48)),
                ("enabled", models.BooleanField(default=False)),
                ("config", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("photographer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="automation_rules", to="accounts.photographerprofile")),
            ],
            options={"ordering": ["pk"]},
        ),
        migrations.CreateModel(
            name="AutomationExecution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_key", models.CharField(max_length=255)),
                ("trigger", models.CharField(choices=[("booking_confirmed", "Booking confirmed"), ("contract_signed", "Contract signed"), ("invoice_due", "Invoice due"), ("payment_received", "Payment received"), ("shoot_completed", "Shoot completed"), ("gallery_published", "Gallery published"), ("gallery_expiring", "Gallery nearing expiration")], max_length=40)),
                ("target_type", models.CharField(max_length=80)),
                ("target_id", models.PositiveBigIntegerField()),
                ("status", models.CharField(choices=[("queued", "Queued"), ("running", "Running"), ("succeeded", "Succeeded"), ("skipped", "Skipped"), ("failed", "Failed")], default="queued", max_length=16)),
                ("message", models.CharField(blank=True, max_length=500)),
                ("error", models.TextField(blank=True)),
                ("context", models.JSONField(blank=True, default=dict)),
                ("queued_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("photographer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="automation_executions", to="accounts.photographerprofile")),
                ("rule", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="executions", to="workflows.automationrule")),
            ],
            options={"ordering": ["-queued_at", "-pk"]},
        ),
        migrations.AddConstraint(
            model_name="automationrule",
            constraint=models.UniqueConstraint(fields=("photographer", "trigger", "action"), name="unique_workflow_rule_per_photographer"),
        ),
        migrations.AddConstraint(
            model_name="automationexecution",
            constraint=models.UniqueConstraint(fields=("rule", "event_key"), name="unique_workflow_execution_event"),
        ),
        migrations.AddIndex(
            model_name="automationexecution",
            index=models.Index(fields=["photographer", "-queued_at"], name="workflow_owner_queued"),
        ),
        migrations.AddIndex(
            model_name="automationexecution",
            index=models.Index(fields=["status", "-queued_at"], name="workflow_status_queued"),
        ),
    ]
