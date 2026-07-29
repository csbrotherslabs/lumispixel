from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client

from .analytics import gallery_analytics_report, track_gallery_event
from .models import Album, AlbumPhoto, Gallery, GalleryAnalyticsEvent, GalleryOrder, GalleryPhoto, GalleryStore, StoreProduct


class GalleryModelTests(TestCase):
    def test_analytics_tracking_and_reports_are_owner_scoped(self):
        user = User.objects.create_user(email="analytics@example.com", password="testpass")
        other_user = User.objects.create_user(email="other-analytics@example.com", password="testpass")
        owner = PhotographerProfile.objects.create(user=user, slug="analytics-owner")
        other = PhotographerProfile.objects.create(user=other_user, slug="other-analytics-owner")
        gallery = Gallery.objects.create(photographer=owner, name="Wedding", slug="analytics-wedding")
        other_gallery = Gallery.objects.create(photographer=other, name="Other", slug="analytics-other")

        track_gallery_event(gallery=gallery, event_type="view", visitor_identifier="opaque-1", session_identifier="session-1", device_category="mobile")
        track_gallery_event(gallery=gallery, event_type="favorite", visitor_identifier="opaque-1", session_identifier="session-1")
        track_gallery_event(gallery=other_gallery, event_type="view", visitor_identifier="opaque-2")
        report = gallery_analytics_report(gallery=gallery)

        self.assertEqual(report["counts"]["views"], 1)
        self.assertEqual(report["counts"]["favorites"], 1)
        self.assertEqual(report["counts"]["visitors"], 1)
        self.assertEqual(GalleryAnalyticsEvent.objects.for_photographer(owner).count(), 2)

    def test_analytics_event_rejects_cross_gallery_photo(self):
        user = User.objects.create_user(email="analytics-photo@example.com", password="testpass")
        owner = PhotographerProfile.objects.create(user=user, slug="analytics-photo-owner")
        gallery = Gallery.objects.create(photographer=owner, name="First", slug="analytics-first")
        other_gallery = Gallery.objects.create(photographer=owner, name="Second", slug="analytics-second")
        photo = GalleryPhoto.objects.create(gallery=other_gallery, photographer=owner, file="other.jpg", original_name="other.jpg")

        with self.assertRaises(ValidationError):
            track_gallery_event(gallery=gallery, event_type="photo_view", photo=photo)

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

    def test_store_product_and_order_enforce_owner_boundaries(self):
        first_user = User.objects.create_user(email="store@example.com", password="testpass")
        second_user = User.objects.create_user(email="other-store@example.com", password="testpass")
        owner = PhotographerProfile.objects.create(user=first_user, slug="store-owner")
        other = PhotographerProfile.objects.create(user=second_user, slug="other-store-owner")
        gallery = Gallery.objects.create(photographer=owner, name="Store Gallery", slug="store-gallery")
        store = GalleryStore.objects.create(photographer=owner, gallery=gallery, name="Keepsakes")

        product = StoreProduct(store=store, gallery=gallery, photographer=other, name="Print", product_type=StoreProduct.ProductType.PRINT, price="25.00")
        with self.assertRaises(ValidationError):
            product.full_clean()
        order = GalleryOrder(store=store, gallery=gallery, photographer=other, order_number="LP-100", customer_name="Client", customer_email="client@example.com")
        with self.assertRaises(ValidationError):
            order.full_clean()

    def test_sale_price_must_be_lower_than_regular_price(self):
        user = User.objects.create_user(email="pricing@example.com", password="testpass")
        owner = PhotographerProfile.objects.create(user=user, slug="pricing-owner")
        gallery = Gallery.objects.create(photographer=owner, name="Pricing", slug="pricing")
        store = GalleryStore.objects.create(photographer=owner, gallery=gallery)
        product = StoreProduct(store=store, gallery=gallery, photographer=owner, name="Download", product_type=StoreProduct.ProductType.DIGITAL, price="10.00", sale_price="10.00")
        with self.assertRaises(ValidationError):
            product.full_clean()
