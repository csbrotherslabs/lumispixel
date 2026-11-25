from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0013_photographerwebsiteequipment"),
        ("clients", "0024_financial_integrity_constraints"),
    ]
    operations = [
        migrations.CreateModel(
            name="PlatformBooking",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ("photographer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="accounts.photographerprofile")),
                ("session", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="platform_booking", to="clients.clientsession")),
            ],
        ),
        migrations.CreateModel(
            name="BookingReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rating", models.PositiveSmallIntegerField()),
                ("comment", models.TextField(max_length=3000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("booking", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="review", to="marketplace.platformbooking")),
            ],
            options={"ordering": ("-created_at", "-pk")},
        ),
        migrations.AddConstraint(model_name="bookingreview", constraint=models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name="marketplace_review_rating_range")),
    ]
