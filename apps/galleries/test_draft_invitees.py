from types import SimpleNamespace
from unittest.mock import patch
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from .test_invitation_email import GalleryInvitationEmailTests
from .models import AccessToken, Gallery, GalleryInvitation
from .services import GalleryInvitationDeliveryError
from .account_views import available_invitations_for_user


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', PUBLIC_BASE_URL='https://lumispixel.com')
class DraftInviteeTests(TestCase):
    setUp = GalleryInvitationEmailTests.setUp

    def save_draft(self):
        self.gallery.status = Gallery.Status.DRAFT
        self.gallery.save(update_fields=['status'])
        return self.client.post(reverse('galleries:prepare_client_gallery_invitation', args=[self.gallery.pk]),
            {'client_name':'Client', 'email':'CLIENT@example.com'})

    def publish(self):
        self.gallery.status = Gallery.Status.PUBLISHED
        self.gallery.save(update_fields=['status'])

    def test_save_draft_is_idempotent_and_creates_no_email_or_access(self):
        self.save_draft()
        self.save_draft()
        invite = self.gallery.invitations.get()
        self.assertEqual(invite.email, 'client@example.com')
        self.assertEqual(invite.status, GalleryInvitation.Status.NOT_SENT)
        self.assertFalse(invite.access_tokens.exists())
        self.assertEqual(len(mail.outbox), 0)
        # Merely publishing never admits a saved client to account galleries.
        self.publish()
        user = SimpleNamespace(is_authenticated=True, email_verified=True, email=invite.email)
        self.assertFalse(available_invitations_for_user(user).exists())

    def test_unsent_invitation_blocks_even_a_manually_issued_token(self):
        self.save_draft(); self.publish()
        invite = self.gallery.invitations.get()
        _, token = AccessToken.issue(invite)
        self.client.logout()
        response = self.client.get(reverse('galleries:client_gallery_access', args=[token]))
        self.assertEqual(response.status_code, 404)

    def test_publish_does_not_email_and_exposes_explicit_send_action(self):
        self.save_draft()
        workspace = reverse('photographer_workspace:gallery_workspace', args=[self.gallery.pk])
        response = self.client.post(workspace, {'action':'publish_gallery'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(AccessToken.objects.exists())
        response = self.client.get(workspace+'?tab=client-access')
        self.assertContains(response, 'Send invitations (1)')
        self.assertContains(response, 'Not sent')

    def test_draft_blocks_individual_and_bulk_send(self):
        self.save_draft()
        invite = self.gallery.invitations.get()
        self.client.post(reverse('galleries:resend_client_gallery_invitation', args=[self.gallery.pk,invite.pk]))
        self.client.post(reverse('galleries:send_saved_gallery_invitations', args=[self.gallery.pk]))
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(AccessToken.objects.exists())

    def test_explicit_bulk_send_skips_sent_and_is_idempotent(self):
        self.save_draft(); self.publish()
        GalleryInvitation.objects.create(gallery=self.gallery, client_name='Already sent',email='sent@example.com')
        url = reverse('galleries:send_saved_gallery_invitations',args=[self.gallery.pk])
        self.client.post(url); self.client.post(url)
        self.assertEqual(len(mail.outbox),1)
        invite=self.gallery.invitations.get(email='client@example.com')
        self.assertEqual(invite.status,GalleryInvitation.Status.PENDING)
        self.assertEqual(invite.access_tokens.filter(revoked_at__isnull=True).count(),1)

    def test_failed_first_send_stays_unsent_and_retry_works(self):
        self.save_draft(); self.publish()
        invite=self.gallery.invitations.get()
        url=reverse('galleries:resend_client_gallery_invitation',args=[self.gallery.pk,invite.pk])
        with patch('apps.galleries.invitation_views.send_gallery_invitation_email',side_effect=GalleryInvitationDeliveryError):
            self.client.post(url)
        invite.refresh_from_db()
        self.assertEqual(invite.status,GalleryInvitation.Status.NOT_SENT)
        self.assertFalse(invite.access_tokens.filter(revoked_at__isnull=True).exists())
        self.client.post(url)
        invite.refresh_from_db()
        self.assertEqual(invite.status,GalleryInvitation.Status.PENDING)
        self.assertEqual(len(mail.outbox),1)

    def test_invalid_email_is_not_saved(self):
        self.client.post(reverse('galleries:prepare_client_gallery_invitation',args=[self.gallery.pk]),
            {'client_name':'Client','email':'not-an-email'})
        self.assertFalse(self.gallery.invitations.exists())

    def test_other_studio_cannot_send_saved_invitations(self):
        self.save_draft(); self.publish()
        from apps.accounts.models import User, PhotographerProfile
        other=User.objects.create_user(email='other-owner@example.com',password='test',primary_role='photographer',email_verified=True,account_status='active')
        PhotographerProfile.objects.create(user=other,slug='other-owner',onboarding_completed=True)
        self.client.force_login(other)
        response=self.client.post(reverse('galleries:send_saved_gallery_invitations',args=[self.gallery.pk]))
        self.assertEqual(response.status_code,404)
        self.assertEqual(len(mail.outbox),0)

    def test_legacy_workspace_invite_and_resend_respect_draft(self):
        self.gallery.status=Gallery.Status.DRAFT;self.gallery.save(update_fields=['status'])
        workspace=reverse('photographer_workspace:gallery_workspace',args=[self.gallery.pk])
        self.client.post(workspace,{'action':'invite','client_name':'Client','email':'client@example.com'})
        invite=self.gallery.invitations.get()
        self.client.post(workspace,{'action':'resend','invitation_id':invite.pk})
        self.assertEqual(invite.status,GalleryInvitation.Status.NOT_SENT)
        self.assertEqual(len(mail.outbox),0)
        self.assertFalse(AccessToken.objects.exists())

    def test_bulk_partial_failure_retries_only_unsent_clients(self):
        self.save_draft(); self.publish()
        GalleryInvitation.objects.create(gallery=self.gallery,client_name='Second',email='second@example.com',status=GalleryInvitation.Status.NOT_SENT)
        from .services import send_gallery_invitation_email
        def selective(request, *, invitation, raw_token):
            if invitation.email == 'second@example.com':
                raise GalleryInvitationDeliveryError
            return send_gallery_invitation_email(request,invitation=invitation,raw_token=raw_token)
        url=reverse('galleries:send_saved_gallery_invitations',args=[self.gallery.pk])
        with patch('apps.galleries.invitation_views.send_gallery_invitation_email',side_effect=selective):
            self.client.post(url)
        self.assertEqual(len(mail.outbox),1)
        self.assertEqual(self.gallery.invitations.filter(status=GalleryInvitation.Status.NOT_SENT).count(),1)
        self.client.post(url)
        self.assertEqual(len(mail.outbox),2)
        self.assertEqual(mail.outbox[-1].to,['second@example.com'])

    def test_bulk_send_is_post_only(self):
        response=self.client.get(reverse('galleries:send_saved_gallery_invitations',args=[self.gallery.pk]))
        self.assertEqual(response.status_code,405)
