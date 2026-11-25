"""Approval transitions for public marketplace bookings."""
import logging
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from apps.clients.models import ClientSession, ClientActivity, ContractTemplate
from apps.clients.contracts import create_contract_from_template
from .models import PlatformBooking

logger = logging.getLogger(__name__)

def notify_photographer(session_id, message):
    session = ClientSession.objects.select_related("photographer__user").get(pk=session_id)
    deliver(session.photographer.user.email, "LumisPixel booking update", message, session)

def deliver(email, subject, message, session):
    try:
        context = {"message": message, "session": session}
        send_mail(subject, render_to_string("marketplace/email/booking_update.txt", context),
                  None, [email], html_message=render_to_string("marketplace/email/booking_update.html", context))
    except Exception:
        logger.exception("Booking notification failed for session %s", session.pk)

@transaction.atomic
def confirm_booking(session, *, actor, client_acknowledgment=False):
    booking = PlatformBooking.objects.select_for_update().get(session_id=session.pk)
    session = ClientSession.objects.select_for_update().get(pk=session.pk)
    if session.status != ClientSession.Status.TENTATIVE or not booking.customer_id or not booking.acknowledged_at:
        raise ValidationError("This booking is not eligible for confirmation.")
    if booking.origin == "photographer":
        if not client_acknowledgment or actor.pk != booking.customer_id:
            raise ValidationError("Only the client can acknowledge this booking.")
    elif client_acknowledgment:
        raise ValidationError("This booking requires photographer approval.")
    session.status = ClientSession.Status.CONFIRMED
    session.save(update_fields=["status", "updated_at"])
    ClientActivity.objects.create(photographer=session.photographer, client=session.client, booking=session,
        actor=actor, event_type=ClientActivity.EventType.BOOKING_UPDATED,
        description="Booking confirmed by the receiving party.", metadata={"origin": booking.origin, "status": "confirmed"})
    template = ContractTemplate.objects.filter(photographer=session.photographer, is_active=True,
        default_specialties__contains=[session.session_type]).order_by("pk").first()
    if template and not session.contracts.exists():
        # An unsigned draft must be reviewed and signed by the photographer.
        create_contract_from_template(booking=session, template=template, actor=None)
    notice = ("Review the generated contract, verify the agreed fee, and sign it before sharing."
              if template else "No default contract is configured. Prepare an agreement before sharing.")
    transaction.on_commit(lambda: notify_photographer(session.pk, "Booking confirmed. " + notice))
    transaction.on_commit(lambda: deliver(booking.client_email or session.client.email,
        "Your LumisPixel booking is confirmed", "Your booking is confirmed. Your photographer will share the contract after review.", session))
