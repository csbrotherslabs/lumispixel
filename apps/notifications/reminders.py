"""Hourly, repeatable scans for time-based notification events."""
from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db.models import F, Sum
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.billing.services import get_allowance, PlanConfigurationError
from apps.clients.models import ClientSession, ClientInvoice, Contract, Lead, ClientTask
from apps.galleries.models import Gallery, GalleryInvitation, GalleryMultipartUpload, GalleryPhoto
from .events import emit, owner_event
from .models import Notification


def local_date(owner, now):
    try:
        return timezone.localdate(now, ZoneInfo(owner.timezone or 'UTC'))
    except ZoneInfoNotFoundError:
        return timezone.localdate(now)


def scan_reminders(*, now=None):
    now = now or timezone.now()
    for booking in ClientSession.objects.filter(status='confirmed', starts_at__gt=now, starts_at__lte=now + timedelta(hours=24)).select_related('photographer__user', 'client__user'):
        owner_event(booking, f'booking-reminder:{booking.pk}:{booking.starts_at.isoformat()}', 'Upcoming session',
                    f'{booking.session_type} starts within 24 hours.', 'bookings', client=True)
    for invoice in ClientInvoice.objects.filter(status__in=['sent', 'partially_paid'], due_date__isnull=False, reminders_enabled=True, amount_paid__lt=F('total')).select_related('photographer__user', 'client__user'):
        today = local_date(invoice.photographer, now)
        if invoice.due_date < today:
            owner_event(invoice, f'invoice-overdue:{invoice.pk}:{invoice.due_date}', 'Invoice overdue',
                        f'Invoice {invoice.invoice_number or invoice.pk} is overdue.', 'invoices', Notification.Category.PAYMENT, client=True)
    for contract in Contract.objects.filter(status__in=['sent', 'viewed'], sent_at__lte=now - timedelta(days=3)).select_related('photographer__user', 'client__user'):
        owner_event(contract, f'contract-reminder:{contract.pk}:{contract.version}:{contract.sent_at}', 'Contract awaiting signature',
                    contract.title, 'contracts', client=True)
    for lead in Lead.objects.filter(next_follow_up__isnull=False, archived_at__isnull=True).exclude(status__in=['booked', 'lost']).select_related('photographer__user'):
        if lead.next_follow_up <= local_date(lead.photographer, now):
            owner_event(lead, f'lead-followup:{lead.pk}:{lead.next_follow_up}', 'Lead follow-up due',
                        f'Follow up with {lead.first_name}.', 'leads', Notification.Category.MESSAGE)
    for task in ClientTask.objects.filter(due_date__isnull=False, status__in=['open', 'in_progress']).select_related('photographer__user'):
        if task.due_date <= local_date(task.photographer, now):
            owner_event(task, f'task-due:{task.pk}:{task.due_date}', 'Follow-up task due', task.title, 'tasks')
    for gallery in Gallery.objects.filter(status__in=['published', 'delivered'], expires_at__gt=now, expires_at__lte=now + timedelta(days=3)).select_related('photographer__user'):
        key = f'gallery-expiration:{gallery.pk}:{gallery.expires_at.isoformat()}'
        emit(recipient=gallery.photographer.user, event_key=key, title='Gallery expires soon', message=f'{gallery.name} expires within 3 days.', category=Notification.Category.GALLERY, action_url=reverse('photographer_workspace:galleries'))
        # Actual active invitations establish eligibility. No broad email broadcast.
        invited = GalleryInvitation.objects.filter(gallery=gallery, status='active').values_list('email', flat=True)
        for email in invited:
            user = User.objects.filter(email__iexact=email, client_profile__isnull=False).first()
            emit(recipient=user, event_key=key, title='Gallery expires soon', message=f'{gallery.name} expires within 3 days.', category=Notification.Category.GALLERY, action_url=reverse('clients:dashboard'))
    for owner in PhotographerProfile.objects.filter(user__is_active=True).select_related('user'):
        try:
            allowance = get_allowance(owner, 'storage_bytes')
        except PlanConfigurationError:
            continue
        if allowance.is_unlimited or allowance.is_custom or allowance.value is None or allowance.value < 0:
            continue
        used = int(Gallery.objects.filter(photographer=owner).aggregate(total=Sum('storage_used'))['total'] or 0)
        full = used >= allowance.value
        if full or (allowance.value and used >= allowance.value * .9):
            threshold = 'full' if full else '90'
            emit(recipient=owner.user, event_key=f'storage:{owner.pk}:{allowance.value}:{threshold}:{now.date()}', title='Storage limit reached' if full else 'Storage nearly full', message='Review your gallery storage or plan allowance.', action_url=reverse('photographer_workspace:billing'))
    # These paths may be updated with QuerySet.update(), bypassing save signals.
    for upload in GalleryMultipartUpload.objects.filter(aborted_at__gte=now - timedelta(hours=24)).select_related('photographer__user', 'gallery'):
        if upload.photographer_id == upload.gallery.photographer_id:
            emit(recipient=upload.photographer.user, event_key=f'upload-stopped:{upload.pk}', title='Upload stopped', message=f'An upload in {upload.gallery.name} was cancelled or interrupted.', category=Notification.Category.GALLERY, action_url=reverse('photographer_workspace:galleries'))
    for photo in GalleryPhoto.objects.filter(status='failed', updated_at__gte=now - timedelta(hours=24)).select_related('photographer__user', 'gallery'):
        if photo.photographer_id == photo.gallery.photographer_id:
            emit(recipient=photo.photographer.user, event_key=f'photo-failed:{photo.pk}', title='Photo processing failed', message=f'A photo in {photo.gallery.name} needs attention.', category=Notification.Category.GALLERY, action_url=reverse('photographer_workspace:galleries'))
