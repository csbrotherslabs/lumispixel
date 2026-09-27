from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import apps.internal_ops.models


class Migration(migrations.Migration):
    dependencies = [
        ("internal_ops", "0002_seed_departments"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SupportTicket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(default=apps.internal_ops.models.support_ticket_reference, editable=False, max_length=16, unique=True)),
                ("requester_type", models.CharField(blank=True, max_length=24)),
                ("category", models.CharField(choices=[("account", "Account & access"), ("billing", "Billing & plan"), ("galleries", "Galleries & delivery"), ("ai", "AI tools"), ("editing", "Editing & culling"), ("website", "Photographer website"), ("booking", "Bookings & calendar"), ("client_access", "Client access"), ("technical", "Technical issue"), ("other", "Other")], max_length=32)),
                ("subject", models.CharField(max_length=180)),
                ("description", models.TextField()),
                ("related_url", models.URLField(blank=True)),
                ("status", models.CharField(choices=[("open", "Open"), ("in_progress", "In progress"), ("waiting_customer", "Waiting on customer"), ("resolved", "Resolved"), ("closed", "Closed")], default="open", max_length=24)),
                ("priority", models.CharField(choices=[("low", "Low"), ("normal", "Normal"), ("high", "High"), ("urgent", "Urgent")], default="normal", max_length=16)),
                ("due_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assignee", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_tickets", to="internal_ops.employeeprofile")),
                ("queue", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="support_tickets", to="internal_ops.department")),
                ("requester", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="support_tickets", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="SupportTicketComment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.TextField()),
                ("is_internal", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("author_employee", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ticket_comments", to="internal_ops.employeeprofile")),
                ("author_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="support_ticket_comments", to=settings.AUTH_USER_MODEL)),
                ("ticket", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="internal_ops.supportticket")),
            ],
            options={"ordering": ("created_at",)},
        ),
        migrations.AddIndex(model_name="supportticket", index=models.Index(fields=["status", "priority", "created_at"], name="support_ticket_queue_idx")),
        migrations.AddIndex(model_name="supportticket", index=models.Index(fields=["assignee", "status"], name="support_ticket_owner_idx")),
        migrations.AddIndex(model_name="supportticket", index=models.Index(fields=["requester", "created_at"], name="support_ticket_req_idx")),
    ]
