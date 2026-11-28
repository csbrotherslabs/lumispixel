"""Read-only business-to-outbox checks; never reconstruct a secret or resend."""
from datetime import timedelta
from django.db.models import Exists, OuterRef, Value, CharField
from django.db.models.functions import Cast, Concat
from django.utils import timezone
from apps.clients.models import ClientInvoice, Contract
from .models import EmailDelivery

def missing_email_queries():
    # Recent cohort avoids treating all pre-outbox historical sends as missing.
    # Explicit deployment cutoff is required to enable these checks.
    from django.conf import settings
    from django.utils.dateparse import parse_datetime
    cutoff = parse_datetime(getattr(settings, "EMAIL_RECONCILIATION_START", "") or "")
    if not cutoff or timezone.is_naive(cutoff):
        return {}
    grace = timezone.now() - timedelta(minutes=15)
    invoices = ClientInvoice.objects.filter(sent_at__gte=cutoff, sent_at__lte=grace,
        status__in=[ClientInvoice.Status.SENT, ClientInvoice.Status.PARTIALLY_PAID, ClientInvoice.Status.PAID])
    invoices = invoices.annotate(expected_key=Concat(Value("invoice:"), Cast("photographer_id", CharField()), Value(":"), Cast("pk", CharField()), Value(":issue")))
    signed = Contract.objects.filter(status=Contract.Status.SIGNED, signed_at__gte=cutoff, signed_at__lte=grace)
    signed = signed.annotate(expected_key=Concat(Value("contract.signed:"), Cast("pk", CharField()), Value(":"), "review_token_digest"))
    review = Contract.objects.filter(status__in=[Contract.Status.SENT, Contract.Status.VIEWED], last_sent_at__gte=cutoff, last_sent_at__lte=grace)
    review = review.annotate(expected_key=Concat(Value("contract.review:"), Cast("pk", CharField()), Value(":"), "review_token_digest"))
    from django.contrib.auth import get_user_model
    from apps.marketplace.models import PlatformBooking
    from apps.dashboard.models import StudioMembership
    users = get_user_model().objects.filter(date_joined__gte=cutoff, date_joined__lte=grace,
        is_active=True, email_verified=False, account_status="pending_email_verification")
    users = users.annotate(expected_prefix=Concat(Value("account.verify:"), Cast("pk", CharField()), Value(":")))
    bookings = PlatformBooking.objects.filter(created_at__gte=cutoff, created_at__lte=grace,
        acknowledged_at__isnull=True, verification_expires_at__gt=timezone.now(),
        session__status="tentative").annotate(expected_key=Concat(Value("booking.acknowledgment:"), Cast("pk", CharField())))
    studio = StudioMembership.objects.filter(status=StudioMembership.Status.INVITED,
        invitation_sent_at__gte=cutoff, invitation_sent_at__lte=grace,
        invitation_expires_at__gt=timezone.now()).annotate(expected_key=Concat(Value("studio.invite:"), Cast("pk", CharField()), Value(":"), "invitation_token_digest"))
    results = {kind: qs.annotate(has_email=Exists(EmailDelivery.objects.filter(event_key=OuterRef("expected_key")))).filter(has_email=False)
            for kind, qs in (("invoice_issue", invoices), ("contract_signed", signed), ("contract_review", review), ("booking_acknowledgment", bookings), ("studio_invitation", studio))}
    results["account_verification"] = users.annotate(has_email=Exists(
        EmailDelivery.objects.filter(event_key__startswith=OuterRef("expected_prefix")))).filter(has_email=False)
    return results

def snapshot():
    return [{"kind": kind, "count": qs.count(), "sample_ids": list(qs.order_by("pk").values_list("pk", flat=True)[:25])}
            for kind, qs in missing_email_queries().items()]
