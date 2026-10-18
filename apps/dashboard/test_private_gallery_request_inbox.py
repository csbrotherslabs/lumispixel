from django.test import SimpleTestCase
from django.urls import reverse


class PrivateGalleryInboxRouteTests(SimpleTestCase):
    def test_route_resolves(self):
        self.assertEqual(reverse('photographer_workspace:private_gallery_requests'), '/photographer/workspace/galleries/access-requests/')
