from django.core.exceptions import PermissionDenied


def is_active_account(user):
    return user.is_authenticated and getattr(user, "can_login", False)


def has_verified_email(user):
    return is_active_account(user) and user.email_verified


def has_client_profile(user):
    return is_active_account(user) and user.has_client_profile


def has_photographer_profile(user):
    return is_active_account(user) and user.has_photographer_profile


def is_verified_photographer(user):
    return has_photographer_profile(user) and user.photographer_profile.is_verified


def is_staff_user(user):
    return is_active_account(user) and user.is_staff


def require_permission(user, predicate):
    if not predicate(user):
        raise PermissionDenied
    return True
