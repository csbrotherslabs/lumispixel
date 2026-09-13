def internal_workspace(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"can_access_internal_workspace": False}

    profile = getattr(request.user, "employee_profile", None)
    return {
        "can_access_internal_workspace": bool(profile and profile.can_access_internal),
        "internal_employee_profile": profile,
    }
