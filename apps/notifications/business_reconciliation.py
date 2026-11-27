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
    return {kind: qs.annotate(has_email=Exists(EmailDelivery.objects.filter(event_key=OuterRef("expected_key")))).filter(has_email=False)
            for kind, qs in (("invoice_issue", invoices), ("contract_signed", signed), ("contract_review", review))}

def snapshot():
    return [{"kind": kind, "count": qs.count(), "sample_ids": list(qs.order_by("pk").values_list("pk", flat=True)[:25])}
            for kind, qs in missing_email_queries().items()]
