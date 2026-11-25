from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import PhotographerProfile
from apps.clients.models import Client, ClientSession
from .models import BookingReview, PlatformBooking
from .verified_reviews import eligible_bookings


class VerifiedReviewEligibilityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create(email="owner@example.com", email_verified=True, account_status="active")
        self.customer = User.objects.create(email="customer@example.com", email_verified=True, account_status="active")
        self.other = User.objects.create(email="other@example.com", email_verified=True, account_status="active")
        self.photographer = PhotographerProfile.objects.create(user=self.owner, slug="review-test")
        self.client_record = Client.objects.create(photographer=self.photographer, user=self.customer, first_name="Customer")
        self.session = ClientSession.objects.create(photographer=self.photographer, client=self.client_record,
            session_type="Portrait", starts_at=timezone.now()-timedelta(days=2), status=ClientSession.Status.COMPLETED)

    def platform_booking(self):
        return PlatformBooking.objects.create(session=self.session, customer=self.customer, photographer=self.photographer)

    def test_manual_crm_booking_is_not_eligible(self):
        self.assertFalse(eligible_bookings(self.customer, self.photographer).exists())

    def test_only_original_customer_can_review(self):
        booking = self.platform_booking()
        self.assertEqual(list(eligible_bookings(self.customer, self.photographer)), [booking])
        self.assertFalse(eligible_bookings(self.other, self.photographer).exists())
        self.assertFalse(eligible_bookings(self.owner, self.photographer).exists())

    def test_incomplete_cancelled_and_consultation_are_not_eligible(self):
        self.platform_booking()
        for status in (ClientSession.Status.TENTATIVE, ClientSession.Status.CONFIRMED, ClientSession.Status.CANCELLED):
            self.session.status = status
            self.session.save()
            self.assertFalse(eligible_bookings(self.customer, self.photographer).exists())
        self.session.status = ClientSession.Status.COMPLETED
        self.session.event_kind = ClientSession.EventKind.CONSULTATION
        self.session.save()
        self.assertFalse(eligible_bookings(self.customer, self.photographer).exists())

    def test_duplicate_and_invalid_rating_constraints(self):
        booking = self.platform_booking()
        with self.assertRaises(IntegrityError), transaction.atomic():
            BookingReview.objects.create(booking=booking, rating=6, comment="Invalid")
        BookingReview.objects.create(booking=booking, rating=5, comment="Excellent")
        self.assertFalse(eligible_bookings(self.customer, self.photographer).exists())
        with self.assertRaises(IntegrityError), transaction.atomic():
            BookingReview.objects.create(booking=booking, rating=4, comment="Duplicate")

    def test_reassigned_crm_client_cannot_review(self):
        self.platform_booking()
        self.client_record.user = self.other
        self.client_record.save()
        self.assertFalse(eligible_bookings(self.customer, self.photographer).exists())
        self.assertFalse(eligible_bookings(self.other, self.photographer).exists())
