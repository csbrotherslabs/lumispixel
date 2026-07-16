from django.contrib.auth.base_user import BaseUserManager
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def normalize_email(self, email):
        email = super().normalize_email(email)
        return email.lower() if email else email

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        if extra_fields.get("is_staff"):
            raise ValueError("Regular users cannot be staff users.")
        if extra_fields.get("is_superuser"):
            raise ValueError("Regular users cannot be superusers.")
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("email_verified", True)
        extra_fields.setdefault("email_verified_at", timezone.now())
        extra_fields.setdefault("account_status", self.model.AccountStatus.ACTIVE)
        extra_fields.setdefault("primary_role", self.model.PrimaryRole.CLIENT)
        extra_fields.setdefault("last_active_workspace", self.model.Workspace.OPERATIONS)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
