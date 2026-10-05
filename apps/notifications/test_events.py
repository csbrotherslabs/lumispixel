from datetime import timedelta
from unittest.mock import patch
from decimal import Decimal

from django.db import transaction
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User, PhotographerProfile
from apps.clients.models import Client, ClientSession, ClientInvoice, InvoicePayment, Lead, Contract
from apps.galleries.models import Gallery, GalleryAnalyticsEvent, GalleryMultipartUpload, GalleryPhoto
from apps.dashboard.models import StudioMembership, StudioInvitationEvent
from apps.internal_ops.models import SupportTicket, SupportTicketComment
from .events import emit
from .models import Notification, NotificationEventReceipt
from .reminders import scan_reminders


class NotificationEventTests(TestCase):
    def setUp(self):
        self.owner_user = User.objects.create_user(email='event-owner@example.com', password='password')
        self.owner = PhotographerProfile.objects.create(user=self.owner_user, slug='event-owner')
        self.client_user = User.objects.create_user(email='event-client@example.com', password='password')
        self.client_record = Client.objects.create(photographer=self.owner, user=self.client_user, first_name='Client')
        self.other_user = User.objects.create_user(email='event-other@example.com', password='password')
        self.other = PhotographerProfile.objects.create(user=self.other_user, slug='event-other')

    def booking(self, **kwargs):
        values = dict(photographer=self.owner, client=self.client_record, session_type='Portrait', starts_at=timezone.now()+timedelta(hours=12))
        values.update(kwargs)
        return ClientSession.objects.create(**values)

    def titles(self, user):
        return list(Notification.objects.filter(recipient=user).values_list('title', flat=True))

    def test_delivery_is_deduplicated_even_after_dismissal(self):
        args = dict(recipient=self.owner_user, event_key='same-event', title='Test', message='Message')
        first = emit(**args)
        self.assertEqual(emit(**args), first)
        first.delete()
        self.assertIsNone(emit(**args))
        self.assertEqual(NotificationEventReceipt.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 0)

    def test_rollback_does_not_leave_notification_or_receipt(self):
        with self.assertRaises(RuntimeError), transaction.atomic():
            Lead.objects.create(photographer=self.owner, first_name='Rollback')
            raise RuntimeError('rollback')
        self.assertFalse(Notification.objects.exists())
        self.assertFalse(NotificationEventReceipt.objects.exists())

    def test_new_lead_notifies_only_owner(self):
        Lead.objects.create(photographer=self.owner, first_name='Lead', notes='PRIVATE NOTES')
        self.assertIn('New lead', self.titles(self.owner_user))
        self.assertFalse(Notification.objects.filter(recipient=self.other_user).exists())
        self.assertFalse(Notification.objects.filter(message__contains='PRIVATE NOTES').exists())

    def test_booking_transitions_and_rescheduling_notify_participants_once(self):
        booking = self.booking()
        self.assertIn('New booking', self.titles(self.client_user))
        booking.status='confirmed'; booking.save()
        count = Notification.objects.count()
        booking.save()
        self.assertEqual(Notification.objects.count(), count)
        booking.starts_at += timedelta(days=1); booking.save()
        self.assertIn('Booking rescheduled', self.titles(self.owner_user))
        booking.status='cancelled'; booking.save()
        self.assertIn('Booking cancelled', self.titles(self.client_user))

    def test_mismatched_client_does_not_receive_booking(self):
        client = Client.objects.create(photographer=self.other, user=self.other_user, first_name='Other')
        self.booking(client=client)
        self.assertFalse(Notification.objects.filter(recipient=self.other_user).exists())

    def test_contract_and_invoice_statuses_and_payment_failure(self):
        booking=self.booking()
        contract=Contract.objects.create(photographer=self.owner, client=self.client_record, booking=booking, title='Agreement', content='PRIVATE CONTRACT')
        contract.status='sent';contract.save()
        contract.status='signed';contract.save()
        invoice=ClientInvoice.objects.create(photographer=self.owner, client=self.client_record, total=Decimal('100'), status='sent')
        InvoicePayment.objects.create(photographer=self.owner, invoice=invoice, amount=Decimal('10'), status='failed')
        self.assertIn('Contract signed', self.titles(self.owner_user))
        self.assertIn('Invoice sent', self.titles(self.client_user))
        self.assertIn('Payment failed', self.titles(self.owner_user))
        self.assertFalse(Notification.objects.filter(message__contains='PRIVATE CONTRACT').exists())

    def test_gallery_activity_recipient_and_no_self_notification(self):
        gallery=Gallery.objects.create(photographer=self.owner, name='Gallery')
        event=GalleryAnalyticsEvent.objects.create(photographer=self.owner, gallery=gallery, event_type='favorite', authenticated_user=self.client_user)
        self.assertIn('Photo favorited', self.titles(self.owner_user))
        count=Notification.objects.count();event.save()
        GalleryAnalyticsEvent.objects.create(photographer=self.owner, gallery=gallery, event_type='favorite', authenticated_user=self.owner_user)
        self.assertEqual(Notification.objects.count(), count)

    def test_password_change_does_not_emit_for_unsaved_password(self):
        self.owner_user.set_password('new-secret')
        self.owner_user.save(update_fields=['last_login'])
        self.assertNotIn('Your password changed', self.titles(self.owner_user))
        self.owner_user.save(update_fields=['password'])
        self.assertIn('Your password changed', self.titles(self.owner_user))
        self.assertFalse(Notification.objects.filter(message__contains='new-secret').exists())

    def test_support_reply_hides_internal_comments(self):
        ticket=SupportTicket.objects.create(reference='T-EVENT', requester=self.client_user, category='technical', subject='Help', description='Help')
        SupportTicketComment.objects.create(ticket=ticket, author_user=self.owner_user, body='PRIVATE STAFF NOTE', is_internal=True)
        self.assertNotIn('Support replied to your ticket', self.titles(self.client_user))
        SupportTicketComment.objects.create(ticket=ticket, author_user=self.owner_user, body='Public reply')
        self.assertIn('Support replied to your ticket', self.titles(self.client_user))
        ticket.status='resolved';ticket.save()
        self.assertIn('Support ticket resolved', self.titles(self.client_user))

    def test_team_invitation_goes_to_invited_account(self):
        member=StudioMembership.objects.create(studio=self.owner, invitation_email=self.client_user.email)
        StudioInvitationEvent.objects.create(membership=member, action='sent')
        self.assertIn('Studio team invitation', self.titles(self.client_user))

    def test_reminders_repeat_without_duplicates_and_skip_paid_invoice(self):
        now=timezone.now()
        self.booking(status='confirmed')
        Lead.objects.create(photographer=self.owner, first_name='Follow', next_follow_up=now.date())
        ClientInvoice.objects.create(photographer=self.owner, client=self.client_record, total=Decimal('100'), status='sent', due_date=now.date()-timedelta(days=1))
        ClientInvoice.objects.create(photographer=self.owner, client=self.client_record, total=Decimal('100'), amount_paid=Decimal('100'), status='paid', due_date=now.date()-timedelta(days=1))
        scan_reminders(now=now)
        count=Notification.objects.count();scan_reminders(now=now)
        self.assertEqual(Notification.objects.count(), count)
        self.assertIn('Upcoming session', self.titles(self.client_user))
        self.assertEqual(Notification.objects.filter(recipient=self.client_user, title='Invoice overdue').count(), 1)
        self.assertIn('Lead follow-up due', self.titles(self.owner_user))

    def test_gallery_expiry_and_upload_failures_are_repeatable(self):
        now=timezone.now()
        gallery=Gallery.objects.create(photographer=self.owner, name='Expiring', status='published', expires_at=now+timedelta(days=1))
        GalleryPhoto.objects.create(photographer=self.owner, gallery=gallery, original_name='photo.jpg', status='failed')
        GalleryMultipartUpload.objects.create(photographer=self.owner, gallery=gallery, object_key='key', upload_id='upload', original_name='photo.jpg', content_type='image/jpeg', file_size=1, aborted_at=now)
        scan_reminders(now=now); count=Notification.objects.count(); scan_reminders(now=now)
        self.assertEqual(Notification.objects.count(), count)
        self.assertIn('Gallery expires soon', self.titles(self.owner_user))
        self.assertIn('Photo processing failed', self.titles(self.owner_user))
        self.assertIn('Upload stopped', self.titles(self.owner_user))

    def test_storage_warning_uses_plan_allowance(self):
        from apps.billing.models import PlanAllowance
        allowance=PlanAllowance.objects.get(plan=self.owner.billing_subscription.plan, key='storage_bytes')
        Gallery.objects.create(photographer=self.owner, name='Storage', storage_used=allowance.value)
        scan_reminders()
        self.assertIn('Storage limit reached', self.titles(self.owner_user))

    def test_dismissed_failed_photo_notice_is_not_recreated_by_scan(self):
        gallery = Gallery.objects.create(photographer=self.owner, name='Failure')
        photo = GalleryPhoto.objects.create(photographer=self.owner, gallery=gallery, original_name='photo.jpg', status='failed')
        Notification.objects.filter(title='Photo processing failed').delete()
        photo.save()
        scan_reminders()
        self.assertNotIn('Photo processing failed', self.titles(self.owner_user))

    def test_unsigned_contract_reminder_is_sent_only_once(self):
        booking = self.booking()
        Contract.objects.create(photographer=self.owner, client=self.client_record, booking=booking, title='Unsigned', content='Agreement', status='sent', sent_at=timezone.now()-timedelta(days=4))
        scan_reminders(); scan_reminders()
        self.assertEqual(Notification.objects.filter(recipient=self.client_user, title='Contract awaiting signature').count(), 1)

    def test_unlimited_storage_does_not_warn(self):
        from apps.billing.services import AllowanceValue
        allowance = AllowanceValue(key='storage_bytes', limit_type='unlimited', value=None, unit='bytes')
        with patch('apps.notifications.reminders.get_allowance', return_value=allowance):
            scan_reminders()
        self.assertNotIn('Storage limit reached', self.titles(self.owner_user))
