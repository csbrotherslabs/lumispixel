def personal_photo_url(user):
    """Use account settings' photo, retaining only the owner's legacy fallback."""
    personal_profile = getattr(user, "client_profile", None)
    if personal_profile is not None:
        return personal_profile.profile_photo.url if personal_profile.profile_photo else ""
    owned_studio = getattr(user, "photographer_profile", None)
    if owned_studio and owned_studio.profile_photo:
        return owned_studio.profile_photo.url
    return ""
