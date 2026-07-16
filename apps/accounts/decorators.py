from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.utils.http import url_has_allowed_host_and_scheme

from . import permissions


def permission_required(predicate):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
            if not predicate(request.user):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


active_account_required = permission_required(permissions.is_active_account)
verified_email_required = permission_required(permissions.has_verified_email)
client_profile_required = permission_required(permissions.has_client_profile)
photographer_profile_required = permission_required(permissions.has_photographer_profile)
verified_photographer_required = permission_required(permissions.is_verified_photographer)
staff_required = permission_required(permissions.is_staff_user)


def safe_next_url(request, url):
    if url and url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return url
    return ""
