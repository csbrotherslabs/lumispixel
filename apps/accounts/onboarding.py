from django.urls import reverse

CLIENT_ONBOARDING_STEPS = {
    1: "clients:onboarding-welcome",
    2: "clients:onboarding-profile",
    3: "clients:onboarding-how-it-works",
}
PHOTOGRAPHER_ONBOARDING_STEPS = {
    1: "photographers:onboarding-welcome",
    2: "photographers:onboarding-profile",
    3: "photographers:onboarding-specialties",
    4: "photographers:onboarding-business",
    5: "photographers:onboarding-theme",
}


def _step_value(profile):
    try:
        return int(profile.onboarding_step)
    except (TypeError, ValueError, AttributeError):
        return 1


def get_client_onboarding_resume_url(profile):
    return reverse(CLIENT_ONBOARDING_STEPS.get(_step_value(profile), CLIENT_ONBOARDING_STEPS[1]))


def get_photographer_onboarding_resume_url(profile):
    return reverse(PHOTOGRAPHER_ONBOARDING_STEPS.get(_step_value(profile), PHOTOGRAPHER_ONBOARDING_STEPS[1]))
