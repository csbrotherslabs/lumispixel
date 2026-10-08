from django.test import TestCase, Client as TestClient
from django.urls import reverse

from apps.accounts.models import PhotographerProfile, User
from apps.dashboard.models import StudioMembership
from apps.galleries.models import Gallery, GalleryInvitation, GalleryPhoto, GalleryPhotoComment, GalleryPhotoCommentReaction


class PhotoPreviewCommentTests(TestCase):
    def setUp(self):
        self.owner = self.user("comment-owner@example.com")
        self.studio = PhotographerProfile.objects.create(user=self.owner, slug="comment-owner", onboarding_completed=True)
        self.gallery = Gallery.objects.create(photographer=self.studio, name="Wedding", slug="comment-wedding")
        self.photo = GalleryPhoto.objects.create(gallery=self.gallery, photographer=self.studio, file="test.jpg", original_name="test.jpg")
        self.invitation = GalleryInvitation.objects.create(gallery=self.gallery, client_name="Emma", email="guest@example.com")
        self.comment = GalleryPhotoComment.objects.create(gallery=self.gallery, photo=self.photo, invitation=self.invitation, body="Lovely photo!")
        self.client.force_login(self.owner)

    def user(self, email):
        return User.objects.create_user(email=email, password="test-pass", primary_role=User.PrimaryRole.PHOTOGRAPHER, email_verified=True, account_status=User.AccountStatus.ACTIVE)

    def action(self, action, comment=None, **kwargs):
        return self.client.post(reverse("photographer_workspace:gallery_photo_comment_action", args=[self.photo.pk, (comment or self.comment).pk]), {"action": action, **kwargs})

    def test_comments_render_and_escape_client_text(self):
        self.comment.body = "<script>alert(1)</script>"
        self.comment.save()
        response = self.client.get(reverse("photographer_workspace:gallery_photo_comments", args=[self.photo.pk]))
        self.assertContains(response, "Emma")
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")

    def test_reaction_switch_and_toggle_persist(self):
        self.assertEqual(self.action("like").status_code, 200)
        self.assertEqual(GalleryPhotoCommentReaction.objects.get(comment=self.comment, user=self.owner).value, 1)
        self.action("dislike")
        self.assertEqual(GalleryPhotoCommentReaction.objects.get(comment=self.comment, user=self.owner).value, -1)
        self.action("dislike")
        self.assertFalse(GalleryPhotoCommentReaction.objects.filter(comment=self.comment, user=self.owner).exists())

    def test_reply_is_in_existing_client_thread(self):
        self.assertEqual(self.action("reply", body="Thank you!").status_code, 200)
        reply = self.comment.replies.get()
        self.assertEqual(reply.author, self.owner)
        self.assertEqual(reply.photo, self.photo)
        self.assertEqual(reply.invitation, self.invitation)
        self.assertEqual(reply.body, "Thank you!")
        self.assertEqual(reply.display_author, "Photographer")
        self.assertTrue(self.photo.client_comments.filter(pk=reply.pk).exists())

    def test_reply_to_reply_stays_in_same_thread(self):
        self.action("reply", body="First")
        reply = self.comment.replies.get()
        self.action("reply", comment=reply, body="Second")
        self.assertEqual(self.comment.replies.count(), 2)

    def test_invalid_replies_and_actions_do_not_write(self):
        for body in ("", "   ", "a" * 2001):
            self.assertEqual(self.action("reply", body=body).status_code, 400)
        self.assertEqual(self.action("unknown").status_code, 400)
        self.assertEqual(self.comment.replies.count(), 0)

    def test_other_studio_cannot_read_or_react(self):
        other = self.user("comment-other@example.com")
        PhotographerProfile.objects.create(user=other, slug="comment-other", onboarding_completed=True)
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("photographer_workspace:gallery_photo_comments", args=[self.photo.pk])).status_code, 404)
        self.assertEqual(self.action("like").status_code, 404)

    def test_comment_from_another_photo_cannot_be_mutated(self):
        photo = GalleryPhoto.objects.create(gallery=self.gallery, photographer=self.studio, file="other.jpg", original_name="other.jpg")
        comment = GalleryPhotoComment.objects.create(gallery=self.gallery, photo=photo, invitation=self.invitation, body="Other")
        self.assertEqual(self.action("like", comment=comment).status_code, 404)

    def test_unassigned_worker_cannot_read_comments(self):
        worker = self.user("comment-worker@example.com")
        StudioMembership.objects.create(studio=self.studio, user=worker, role=StudioMembership.Role.PHOTOGRAPHER, status=StudioMembership.Status.ACTIVE)
        self.client.force_login(worker)
        self.assertEqual(self.client.get(reverse("photographer_workspace:gallery_photo_comments", args=[self.photo.pk])).status_code, 404)

    def test_csrf_required_for_comment_mutations(self):
        client = TestClient(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(reverse("photographer_workspace:gallery_photo_comment_action", args=[self.photo.pk, self.comment.pk]), {"action": "like"}).status_code, 403)

    def test_sort_comments_in_both_directions(self):
        later = GalleryPhotoComment.objects.create(gallery=self.gallery, photo=self.photo, invitation=self.invitation, body="Newest comment")
        url = reverse("photographer_workspace:gallery_photo_comments", args=[self.photo.pk])
        newest = self.client.get(url, {"sort": "newest"})
        oldest = self.client.get(url, {"sort": "oldest"})
        self.assertLess(newest.content.index(b"Newest comment"), newest.content.index(b"Lovely photo!"))
        self.assertLess(oldest.content.index(b"Lovely photo!"), oldest.content.index(b"Newest comment"))
        self.assertEqual(self.client.get(url, {"sort": "invalid"}).status_code, 400)

    def test_photographer_can_start_a_comment_without_an_invitation(self):
        self.invitation.delete()
        response = self.client.post(reverse("photographer_workspace:gallery_photo_comment_create", args=[self.photo.pk]), {"body": "Please review this edit."})
        self.assertEqual(response.status_code, 200)
        comment = self.photo.client_comments.get()
        self.assertEqual(comment.author, self.owner)
        self.assertIsNone(comment.parent)
        self.assertIsNone(comment.invitation)
        self.assertTrue(comment.is_studio_comment)
        self.assertEqual(comment.display_author, "Photographer")
        self.assertEqual(self.action("reply", comment=comment, body="Followup").status_code, 200)
        self.assertEqual(comment.replies.get().body, "Followup")

    def test_photographer_comment_validation_and_scope(self):
        url = reverse("photographer_workspace:gallery_photo_comment_create", args=[self.photo.pk])
        for body in ("", "   ", "a" * 2001):
            self.assertEqual(self.client.post(url, {"body": body}).status_code, 400)
        other = self.user("comment-new-other@example.com")
        PhotographerProfile.objects.create(user=other, slug="comment-new-other", onboarding_completed=True)
        self.client.force_login(other)
        self.assertEqual(self.client.post(url, {"body": "Unauthorized"}).status_code, 404)
        self.assertEqual(self.photo.client_comments.count(), 1)

    def test_new_comment_requires_csrf(self):
        client = TestClient(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(reverse("photographer_workspace:gallery_photo_comment_create", args=[self.photo.pk]), {"body": "No token"}).status_code, 403)

    def test_author_can_delete_comment_and_replies(self):
        comment = GalleryPhotoComment.objects.create(gallery=self.gallery, photo=self.photo, author=self.owner, body="My note")
        self.action("reply", comment=comment, body="My reply")
        self.action("like", comment=comment)
        self.assertEqual(self.action("delete", comment=comment).status_code, 200)
        self.assertFalse(GalleryPhotoComment.objects.filter(pk=comment.pk).exists())
        self.assertFalse(GalleryPhotoCommentReaction.objects.filter(comment_id=comment.pk).exists())

    def test_photographer_cannot_delete_client_comment(self):
        self.assertEqual(self.action("delete").status_code, 403)
        self.assertTrue(GalleryPhotoComment.objects.filter(pk=self.comment.pk).exists())

    def test_only_author_sees_workspace_delete_control(self):
        own = GalleryPhotoComment.objects.create(gallery=self.gallery, photo=self.photo, author=self.owner, body="My note")
        response = self.client.get(reverse("photographer_workspace:gallery_photo_comments", args=[self.photo.pk]))
        self.assertContains(response, "data-comment-delete", count=1)
