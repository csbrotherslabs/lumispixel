from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def internal_employee_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        profile = getattr(request.user, "employee_profile", None)
        if profile is None or not profile.can_access_internal:
            raise PermissionDenied("Active LumisPixel employee access is required.")
        request.employee_profile = profile
        return view_func(request, *args, **kwargs)

    return wrapped
