import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import escape

from .models import EmployeeProfile


logger = logging.getLogger(__name__)


def _base_url():
    return (getattr(settings, "PUBLIC_BASE_URL", "") or "https://lumispixel.com").rstrip("/")


def _customer_ticket_url(ticket):
    return f"{_base_url()}/resources/help-center/tickets/{ticket.reference}/"


def _internal_ticket_url(ticket):
    return f"{_base_url()}/internal/tickets/{ticket.reference}/"


def _support_recipients(ticket):
    if ticket.assignee and ticket.assignee.status == EmployeeProfile.Status.ACTIVE:
        email = ticket.assignee.user.email
        return [email] if email else []
    if not ticket.queue_id:
        return []
    return list(
        EmployeeProfile.objects.filter(
            status=EmployeeProfile.Status.ACTIVE,
            department_id=ticket.queue_id,
            user__is_active=True,
        )
        .exclude(user__email="")
        .values_list("user__email", flat=True)
        .distinct()
    )


def _send(subject, plain_body, html_body, recipients):
    recipients = [email for email in dict.fromkeys(recipients or []) if email]
    if not recipients:
        return False
    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body=plain_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
        )
        message.attach_alternative(html_body, "text/html")
        message.send(fail_silently=False)
        return True
    except Exception:
        logger.exception("Support email delivery failed for subject %s", subject)
        return False


def _html(title, intro, ticket, cta_label, cta_url, message_text=""):
    message_block = ""
    if message_text:
        safe_text = escape(message_text).replace("\n", "<br>")
        message_block = f'<div style="margin:18px 0;padding:14px 16px;background:#f7f8fa;border-radius:10px;color:#30343c;line-height:1.6;">{safe_text}</div>'
    safe_title = escape(title)
    safe_intro = escape(intro)
    safe_reference = escape(ticket.reference)
    safe_subject = escape(ticket.subject)
    safe_cta_label = escape(cta_label)
    safe_cta_url = escape(cta_url)
    return f"""
    <div style="font-family:Arial,sans-serif;background:#f6f7f9;padding:28px;color:#171b24;">
      <div style="max-width:620px;margin:0 auto;background:#ffffff;border-radius:16px;padding:28px;border:1px solid #e5e7eb;">
        <div style="font-size:12px;font-weight:700;letter-spacing:.08em;color:#d7193f;text-transform:uppercase;">LumisPixel Support</div>
        <h1 style="font-size:26px;margin:10px 0 12px;">{safe_title}</h1>
        <p style="color:#626875;line-height:1.6;">{safe_intro}</p>
        <div style="margin:18px 0;padding:14px 16px;background:#fafafa;border:1px solid #eceef1;border-radius:10px;">
          <strong>{safe_reference}</strong><br>
          <span style="color:#626875;">{safe_subject}</span>
        </div>
        {message_block}
        <a href="{safe_cta_url}" style="display:inline-block;background:#171b24;color:#fff;text-decoration:none;padding:12px 18px;border-radius:10px;font-weight:700;">{safe_cta_label}</a>
        <p style="margin-top:24px;font-size:12px;color:#8a9099;">This is an automated LumisPixel support notification.</p>
      </div>
    </div>
    """


def notify_ticket_created(ticket):
    customer_subject = f"[{ticket.reference}] We received your LumisPixel support request"
    customer_plain = (
        f"We received your support request {ticket.reference}: {ticket.subject}.\n\n"
        f"View your ticket: {_customer_ticket_url(ticket)}"
    )
    _send(
        customer_subject,
        customer_plain,
        _html(
            "We received your support request",
            "Your ticket has been created and routed to LumisPixel Support.",
            ticket,
            "View support ticket",
            _customer_ticket_url(ticket),
        ),
        [ticket.requester.email],
    )

    support_subject = f"New support ticket {ticket.reference}: {ticket.subject}"
    support_plain = (
        f"New ticket from {ticket.requester.display_name} ({ticket.requester.email}).\n"
        f"Category: {ticket.get_category_display()}\n\n"
        f"Open ticket: {_internal_ticket_url(ticket)}"
    )
    _send(
        support_subject,
        support_plain,
        _html(
            "New support ticket",
            f"{ticket.requester.display_name} submitted a new {ticket.get_category_display().lower()} request.",
            ticket,
            "Open in LumisPixel Internal",
            _internal_ticket_url(ticket),
            ticket.description,
        ),
        _support_recipients(ticket),
    )


def notify_customer_reply(ticket, comment):
    subject = f"Customer replied to {ticket.reference}: {ticket.subject}"
    plain = (
        f"{ticket.requester.display_name} replied to ticket {ticket.reference}.\n\n"
        f"{comment.body}\n\nOpen ticket: {_internal_ticket_url(ticket)}"
    )
    _send(
        subject,
        plain,
        _html(
            "Customer replied",
            f"{ticket.requester.display_name} sent a new reply on this support ticket.",
            ticket,
            "Open in LumisPixel Internal",
            _internal_ticket_url(ticket),
            comment.body,
        ),
        _support_recipients(ticket),
    )


def notify_staff_reply(ticket, comment):
    subject = f"[{ticket.reference}] LumisPixel Support replied"
    plain = (
        f"LumisPixel Support replied to your ticket {ticket.reference}.\n\n"
        f"{comment.body}\n\nView ticket: {_customer_ticket_url(ticket)}"
    )
    _send(
        subject,
        plain,
        _html(
            "LumisPixel Support replied",
            "There is a new message in your support conversation.",
            ticket,
            "View support ticket",
            _customer_ticket_url(ticket),
            comment.body,
        ),
        [ticket.requester.email],
    )


def notify_ticket_status_changed(ticket, old_status):
    if old_status == ticket.status:
        return
    subject = f"[{ticket.reference}] Ticket status updated to {ticket.get_status_display()}"
    plain = (
        f"Your LumisPixel support ticket {ticket.reference} is now {ticket.get_status_display()}.\n\n"
        f"View ticket: {_customer_ticket_url(ticket)}"
    )
    _send(
        subject,
        plain,
        _html(
            "Support ticket status updated",
            f"Your ticket status changed to {ticket.get_status_display()}.",
            ticket,
            "View support ticket",
            _customer_ticket_url(ticket),
        ),
        [ticket.requester.email],
    )


def notify_ticket_assigned(ticket, old_assignee_id):
    if ticket.assignee_id == old_assignee_id or not ticket.assignee:
        return
    subject = f"Assigned support ticket {ticket.reference}: {ticket.subject}"
    plain = f"You have been assigned ticket {ticket.reference}.\n\nOpen ticket: {_internal_ticket_url(ticket)}"
    _send(
        subject,
        plain,
        _html(
            "Support ticket assigned",
            "This ticket is now assigned to you.",
            ticket,
            "Open in LumisPixel Internal",
            _internal_ticket_url(ticket),
        ),
        [ticket.assignee.user.email],
    )
