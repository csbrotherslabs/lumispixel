from django.shortcuts import redirect

from .views import photographer_workspace_required


@photographer_workspace_required
def workspace_help(request):
    """Send photographer workspace users to the real LumisPixel Help Center."""
    return redirect("support_help_center")
