from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User, PhotographerProfile
from apps.clients.models import Client, ClientInvoice, ClientSession
from apps.dashboard.financial_actions import record_payment
from apps.dashboard.financial_automation import queue_booking_reminder, financial_metrics
from apps.notifications.models import EmailDelivery
from apps.notifications.lifecycle import eligible


class FinancialAutomationTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="finance-owner@example.com", password="test",
            email_verified=True, account_status=User.AccountStatus.ACTIVE,
            primary_role=User.PrimaryRole.PHOTOGRAPHER)
        self.profile = PhotographerProfile.objects.create(user=user, slug="finance-auto", onboarding_completed=True)
        self.customer = Client.objects.create(photographer=self.profile, first_name="Client", email="finance-client@example.com")
        self.booking = ClientSession.objects.create(photographer=self.profile, client=self.customer,
            session_type="Portrait", starts_at=timezone.now()+timedelta(days=1), status="confirmed",
            pricing_confirmed=True, booking_value=100, payment_currency="USD")
        self.invoice = ClientInvoice.objects.create(photographer=self.profile, client=self.customer,
            booking=self.booking, invoice_number="INV-AUTO", total=100, status="sent")

    def test_receipt_is_queued_once_and_metrics_distinguish_sent(self):
        data = {"client": self.customer.pk, "invoice": self.invoice.pk, "amount": "50",
                "method": "cash", "submission_key": "receipt-replay"}
        record_payment(self.profile, data)
        record_payment(self.profile, data)
        delivery = EmailDelivery.objects.get(lifecycle_kind="payment.receipt")
        self.assertTrue(eligible(delivery))
        self.assertEqual(financial_metrics()["receipts_sent"], 0)
        self.assertEqual(financial_metrics()["payments_processed"], 1)

    def test_reminder_deduplication_and_paid_suppression(self):
        day = timezone.localdate()
        self.assertTrue(queue_booking_reminder(self.booking.pk, day))
        self.assertFalse(queue_booking_reminder(self.booking.pk, day))
        delivery = EmailDelivery.objects.get(lifecycle_kind="booking.balance")
        self.assertTrue(eligible(delivery))
        record_payment(self.profile, {"client": self.customer.pk, "invoice": self.invoice.pk,
            "amount": "100", "method": "cash", "submission_key": "full-payment"})
        self.assertFalse(eligible(delivery))

    def test_post_event_and_cancelled_booking(self):
        self.booking.starts_at = timezone.now()-timedelta(days=1)
        self.booking.status = "completed"
        self.booking.save()
        self.assertTrue(queue_booking_reminder(self.booking.pk, timezone.localdate()))
        delivery = EmailDelivery.objects.get(lifecycle_kind="booking.balance")
        self.booking.status = "cancelled"
        self.booking.save()
        self.assertFalse(eligible(delivery))
