from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client

from .models import Album, AlbumPhoto, Gallery, GalleryPhoto


class GalleryModelTests(TestCase):
    def test_gallery_defaults_and_owner_scoping(self):
        user = User.objects.create_user(email="owner@example.com", password="testpass", primary_role=User.PrimaryRole.PHOTOGRAPHER)
        other_user = User.objects.create_user(email="other@example.com", password="testpass", primary_role=User.PrimaryRole.PHOTOGRAPHER)
        owner = PhotographerProfile.objects.create(user=user, slug="owner")
        other = PhotographerProfile.objects.create(user=other_user, slug="other")
        gallery = Gallery.objects.create(photographer=owner, name="Wedding", slug="wedding")
        Gallery.objects.create(photographer=other, name="Portrait", slug="portrait")

        self.assertEqual(gallery.status, Gallery.Status.DRAFT)
        self.assertEqual(gallery.visibility, Gallery.Visibility.PRIVATE)
        self.assertEqual(list(Gallery.objects.for_photographer(owner)), [gallery])

    def test_client_must_belong_to_gallery_photographer(self):
        owner_user = User.objects.create_user(email="one@example.com", password="testpass")
        other_user = User.objects.create_user(email="two@example.com", password="testpass")
        owner = PhotographerProfile.objects.create(user=owner_user, slug="one")
        other = PhotographerProfile.objects.create(user=other_user, slug="two")
        client = Client.objects.create(photographer=other, first_name="Wrong owner")

        gallery = Gallery(photographer=owner, client=client, name="Invalid", slug="invalid")
        with self.assertRaises(ValidationError):
            gallery.full_clean()

    def test_album_curates_only_photos_from_its_gallery(self):
        user = User.objects.create_user(email="albums@example.com", password="testpass")
        owner = PhotographerProfile.objects.create(user=user, slug="album-owner")
        gallery = Gallery.objects.create(photographer=owner, name="Wedding", slug="wedding")
        other_gallery = Gallery.objects.create(photographer=owner, name="Portraits", slug="portraits")
        photo = GalleryPhoto.objects.create(gallery=other_gallery, photographer=owner, file="other.jpg", original_name="other.jpg")
        album = Album.objects.create(gallery=gallery, name="Ceremony", visibility=Album.Visibility.CLIENT_ONLY)

        membership = AlbumPhoto(album=album, photo=photo)
        with self.assertRaises(ValidationError):
            membership.full_clean()

        self.assertEqual(list(Album.objects.for_photographer(owner)), [album])
