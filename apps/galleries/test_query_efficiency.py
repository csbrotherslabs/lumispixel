from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection

from apps.accounts.models import PhotographerProfile, User
from apps.galleries.models import Album, AlbumPhoto, Gallery, GalleryPhoto
from apps.galleries.views import CLIENT_GALLERY_PAGE_SIZE, _paginate_client_gallery_photos, _prepare_client_gallery_content


class ClientGalleryQueryEfficiencyTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="query-efficiency@example.com", password="testpass")
        self.studio = PhotographerProfile.objects.create(user=user, slug="query-efficiency")
        self.gallery = Gallery.objects.create(photographer=self.studio, name="Query efficiency", slug="query-efficiency")
        self.photos = GalleryPhoto.objects.bulk_create([
            GalleryPhoto(
                gallery=self.gallery,
                photographer=self.studio,
                file=f"galleries/query/{index}.jpg",
                original_name=f"{index}.jpg",
                file_size=100,
                status=GalleryPhoto.Status.COMPLETED,
                is_visible=True,
            )
            for index in range(CLIENT_GALLERY_PAGE_SIZE)
        ])
        self.albums = [Album.objects.create(gallery=self.gallery, name=f"Album {index}", display_order=index) for index in range(4)]
        AlbumPhoto.objects.bulk_create([
            AlbumPhoto(album=album, photo=photo, position=index)
            for album in self.albums
            for index, photo in enumerate(self.photos[:10])
        ])
        self.factory = RequestFactory()

    @override_settings(MEDIA_SIGNING_SECRET="test-query-efficiency-secret")
    def test_album_membership_preparation_has_constant_query_count(self):
        page, photos = _paginate_client_gallery_photos(self.factory.get("/gallery/"), self.gallery)
        albums = list(Album.objects.filter(gallery=self.gallery).select_related("cover_photo").order_by("display_order", "pk"))
        with CaptureQueriesContext(connection) as queries:
            _prepare_client_gallery_content(self.gallery, photos, albums)
        self.assertLessEqual(len(queries), 1)

    def test_pagination_query_count_does_not_scale_with_photo_count(self):
        request = self.factory.get("/gallery/")
        with CaptureQueriesContext(connection) as queries:
            page, photos = _paginate_client_gallery_photos(request, self.gallery)
            len(photos)
            page.paginator.count
        self.assertLessEqual(len(queries), 2)
        self.assertEqual(len(photos), CLIENT_GALLERY_PAGE_SIZE)
