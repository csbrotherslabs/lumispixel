from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.internal_ops.models import Department, SupportTicket, SupportTicketComment

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
            return redirect("support_ticket_detail", reference=ticket.reference)

    recent_tickets = []
    if request.user.is_authenticated:
        recent_tickets = SupportTicket.objects.filter(requester=request.user).select_related("assignee__user")[:5]

    return render(request, "core/help_center.html", {
        "form": form,
        "submitted_reference": submitted_reference,
        "recent_tickets": recent_tickets,
    })


@login_required
@require_http_methods(["GET", "POST"])
def support_ticket_detail(request, reference):
    ticket = get_object_or_404(
        SupportTicket.objects.select_related("assignee__user", "queue"),
        reference=reference,
        requester=request.user,
    )

    if request.method == "POST":
        body = request.POST.get("body", "").strip()
        if not body:
            messages.error(request, "Enter a reply before sending.")
        elif ticket.status == SupportTicket.Status.CLOSED:
            messages.error(request, "This ticket is closed and can no longer receive replies.")
        else:
            SupportTicketComment.objects.create(
                ticket=ticket,
                author_user=request.user,
                body=body,
                is_internal=False,
            )
            if ticket.status == SupportTicket.Status.WAITING_CUSTOMER:
                ticket.status = SupportTicket.Status.OPEN
                ticket.save(update_fields=["status", "updated_at"])
            messages.success(request, "Your reply was sent to LumisPixel Support.")
            return redirect("support_ticket_detail", reference=ticket.reference)

    conversation = ticket.comments.filter(is_internal=False).select_related("author_employee__user", "author_user")
    return render(request, "core/support_ticket_detail.html", {
        "ticket": ticket,
        "conversation": conversation,
    })
