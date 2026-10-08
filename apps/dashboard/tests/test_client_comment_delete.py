from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User, PhotographerProfile
from apps.galleries.models import AccessToken, Gallery, GalleryInvitation, GalleryPermission, GalleryPhoto, GalleryPhotoComment, GallerySettings


class ClientCommentDeleteTests(TestCase):
    def setUp(self):
        owner = User.objects.create_user(email="delete-studio@example.com", password="testpass")
        studio = PhotographerProfile.objects.create(user=owner, slug="delete-studio")
        self.gallery = Gallery.objects.create(photographer=studio, name="Delete comments", slug="delete-comments", status=Gallery.Status.PUBLISHED, visibility=Gallery.Visibility.PRIVATE, published_at=timezone.now())
        GallerySettings.objects.create(gallery=self.gallery, gallery_url=self.gallery.slug)
        self.permissions = GalleryPermission.objects.create(gallery=self.gallery, comment=True)
        self.invitation = GalleryInvitation.objects.create(gallery=self.gallery, client_name="Guest", email="delete-guest@example.com")
        _, self.token = AccessToken.issue(self.invitation)
        self.photo = GalleryPhoto.objects.create(gallery=self.gallery, photographer=studio, file="test.jpg", original_name="test.jpg", status=GalleryPhoto.Status.COMPLETED)
        self.comment = GalleryPhotoComment.objects.create(gallery=self.gallery, photo=self.photo, invitation=self.invitation, body="My comment")

    def url(self, token=None, photo=None):
        return reverse("galleries:client_gallery_comment_delete", args=[token or self.token, (photo or self.photo).pk, self.comment.pk])

    def test_guest_can_delete_own_invitation_comment(self):
        response = self.client.post(self.url(), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["comment_count"], 0)
        self.assertIn(self.comment.pk, response.json()["deleted_ids"])
        self.assertFalse(GalleryPhotoComment.objects.filter(pk=self.comment.pk).exists())

    def test_other_invitation_cannot_delete_comment(self):
        invitation = GalleryInvitation.objects.create(gallery=self.gallery, client_name="Other", email="delete-other@example.com")
        _, token = AccessToken.issue(invitation)
        self.assertEqual(self.client.post(self.url(token)).status_code, 403)
        self.assertTrue(GalleryPhotoComment.objects.filter(pk=self.comment.pk).exists())

    def test_authenticated_author_required_when_comment_has_author(self):
        author = User.objects.create_user(email="comment-author@example.com", password="testpass", primary_role=User.PrimaryRole.CLIENT, account_status=User.AccountStatus.ACTIVE, email_verified=True, onboarding_completed=True)
        self.comment.author = author
        self.comment.save()
        self.assertEqual(self.client.post(self.url()).status_code, 403)
        self.client.force_login(author)
        self.assertEqual(self.client.post(self.url(), HTTP_X_REQUESTED_WITH="XMLHttpRequest").status_code, 200)

    def test_cross_photo_and_csrf_are_rejected(self):
        photo = GalleryPhoto.objects.create(gallery=self.gallery, photographer=self.gallery.photographer, file="other.jpg", original_name="other.jpg", status=GalleryPhoto.Status.COMPLETED)
        self.assertEqual(self.client.post(self.url(photo=photo)).status_code, 404)
        self.assertEqual(Client(enforce_csrf_checks=True).post(self.url()).status_code, 403)

    def test_delete_requires_post_and_comment_permission(self):
        self.assertEqual(self.client.get(self.url()).status_code, 405)
        self.permissions.comment = False
        self.permissions.save()
        self.assertEqual(self.client.post(self.url()).status_code, 403)
