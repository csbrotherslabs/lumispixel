from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Department",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("code", models.SlugField(max_length=60, unique=True)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="InternalRole",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("code", models.SlugField(max_length=80, unique=True)),
                ("description", models.TextField(blank=True)),
                ("is_executive", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("department", models.ForeignKey(blank=True, help_text="Leave blank for company-wide roles such as Executive or Administrator.", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="roles", to="internal_ops.department")),
            ],
            options={"ordering": ("department__name", "name")},
        ),
        migrations.CreateModel(
            name="EmployeeProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("employee_id", models.CharField(max_length=32, unique=True)),
                ("title", models.CharField(blank=True, max_length=120)),
                ("status", models.CharField(choices=[("invited", "Invited"), ("active", "Active"), ("leave", "On leave"), ("suspended", "Suspended"), ("terminated", "Terminated")], default="invited", max_length=20)),
                ("hire_date", models.DateField(blank=True, null=True)),
                ("last_internal_access_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("department", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="employees", to="internal_ops.department")),
                ("manager", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="direct_reports", to="internal_ops.employeeprofile")),
                ("role", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="employees", to="internal_ops.internalrole")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="employee_profile", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("user__last_name", "user__first_name", "user__email")},
        ),
        migrations.CreateModel(
            name="InternalAuditEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("category", models.CharField(choices=[("access", "Access"), ("employee", "Employee"), ("customer", "Customer"), ("billing", "Billing"), ("ai", "AI"), ("support", "Support"), ("security", "Security"), ("system", "System")], max_length=20)),
                ("action", models.CharField(max_length=120)),
                ("target_type", models.CharField(blank=True, max_length=80)),
                ("target_id", models.CharField(blank=True, max_length=100)),
                ("summary", models.CharField(max_length=255)),
                ("reason", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_events", to="internal_ops.employeeprofile")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddIndex(model_name="internalauditevent", index=models.Index(fields=["category", "created_at"], name="internal_audit_cat_idx")),
        migrations.AddIndex(model_name="internalauditevent", index=models.Index(fields=["actor", "created_at"], name="internal_audit_actor_idx")),
    ]
