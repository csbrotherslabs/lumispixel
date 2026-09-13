from django.contrib import messages
from django.shortcuts import redirect, render

from apps.internal_ops.models import Department, SupportTicket

from .support_forms import SupportTicketIntakeForm


def _requester_type(user):
    if hasattr(user, "photographer_profile"):
        return "photographer"
    if hasattr(user, "client_profile"):
        return "client"
    return "customer"


def help_center(request):
    submitted_reference = request.session.pop("support_ticket_reference", None)
    form = SupportTicketIntakeForm()

    if request.method == "POST":
        if not request.user.is_authenticated:
            messages.info(request, "Sign in to submit a LumisPixel support ticket so we can securely connect it to your account.")
            return redirect("accounts:login")

        form = SupportTicketIntakeForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.requester = request.user
            ticket.requester_type = _requester_type(request.user)
            ticket.queue = Department.objects.filter(code="customer-support", is_active=True).first()
            ticket.save()
            request.session["support_ticket_reference"] = ticket.reference
            return redirect("core:resources_help_center")

    recent_tickets = []
    if request.user.is_authenticated:
        recent_tickets = SupportTicket.objects.filter(requester=request.user).select_related("assignee__user")[:5]

    return render(request, "core/help_center.html", {
        "form": form,
        "submitted_reference": submitted_reference,
        "recent_tickets": recent_tickets,
    })
