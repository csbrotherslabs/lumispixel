from django.test import RequestFactory, TestCase

from apps.accounts.models import PhotographerProfile, User
from apps.galleries.models import Gallery, GalleryPhoto
from apps.galleries.views import CLIENT_GALLERY_PAGE_SIZE, _paginate_client_gallery_photos


class LargeGalleryPaginationTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="large-gallery@example.com", password="testpass")
        self.studio = PhotographerProfile.objects.create(user=user, slug="large-gallery")
        self.gallery = Gallery.objects.create(photographer=self.studio, name="Large gallery", slug="large-gallery")
        GalleryPhoto.objects.bulk_create([
            GalleryPhoto(
                gallery=self.gallery,
                photographer=self.studio,
                file=f"galleries/performance/{index}.jpg",
                original_name=f"{index}.jpg",
                file_size=100,
                status=GalleryPhoto.Status.COMPLETED,
                is_visible=True,
            )
            for index in range(CLIENT_GALLERY_PAGE_SIZE + 15)
        ])
        self.factory = RequestFactory()

    def test_first_page_materializes_only_page_size(self):
        page, photos = _paginate_client_gallery_photos(self.factory.get("/gallery/"), self.gallery)
        self.assertEqual(page.paginator.count, CLIENT_GALLERY_PAGE_SIZE + 15)
        self.assertEqual(len(photos), CLIENT_GALLERY_PAGE_SIZE)
        self.assertTrue(page.has_next())

    def test_second_page_materializes_only_remaining_photos(self):
        page, photos = _paginate_client_gallery_photos(self.factory.get("/gallery/?page=2"), self.gallery)
        self.assertEqual(page.number, 2)
        self.assertEqual(len(photos), 15)

    def test_hidden_and_incomplete_photos_are_not_counted(self):
        GalleryPhoto.objects.create(
            gallery=self.gallery, photographer=self.studio, file="galleries/performance/hidden.jpg",
            original_name="hidden.jpg", file_size=100, status=GalleryPhoto.Status.COMPLETED, is_visible=False,
        )
        GalleryPhoto.objects.create(
            gallery=self.gallery, photographer=self.studio, file="galleries/performance/queued.jpg",
            original_name="queued.jpg", file_size=100, status=GalleryPhoto.Status.QUEUED, is_visible=True,
        )
        page, photos = _paginate_client_gallery_photos(self.factory.get("/gallery/"), self.gallery)
        self.assertEqual(page.paginator.count, CLIENT_GALLERY_PAGE_SIZE + 15)
        self.assertEqual(len(photos), CLIENT_GALLERY_PAGE_SIZE)
