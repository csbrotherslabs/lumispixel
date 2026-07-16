from django.db import transaction

from .models import ClientProfile, PhotographerProfile, User


@transaction.atomic
def create_client_account(*, email, password=None, **user_fields):
    user_fields.setdefault("primary_role", User.PrimaryRole.CLIENT)
    user_fields.setdefault("last_active_workspace", User.Workspace.CLIENT)
    user = User.objects.create_user(email=email, password=password, **user_fields)
    ClientProfile.objects.create(user=user)
    return user


@transaction.atomic
def create_photographer_account(*, email, password=None, create_client_profile=True, **user_fields):
    user_fields.setdefault("primary_role", User.PrimaryRole.PHOTOGRAPHER)
    user_fields.setdefault("last_active_workspace", User.Workspace.PHOTOGRAPHER)
    user = User.objects.create_user(email=email, password=password, **user_fields)
    PhotographerProfile.objects.create(user=user)
    if create_client_profile:
        ClientProfile.objects.create(user=user)
    return user


@transaction.atomic
def enable_client_profile(user):
    profile, _ = ClientProfile.objects.get_or_create(user=user)
    return profile


@transaction.atomic
def enable_photographer_profile(user):
    profile, _ = PhotographerProfile.objects.get_or_create(user=user)
    return profile
