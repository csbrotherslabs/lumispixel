from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from apps.dashboard.views import _workspace_nav


class PrivateGalleryInboxRouteTests(SimpleTestCase):
    def test_route_resolves(self):
        self.assertEqual(reverse('photographer_workspace:private_gallery_requests'), '/photographer/workspace/galleries/access-requests/')

    @override_settings(VISUAL_SEARCH_PRIVATE_ACCESS_REQUESTS_ENABLED=False)
    def test_nav_hidden_by_default(self):
        items = [item for group in _workspace_nav('galleries') for item in group['items']]
        self.assertNotIn('private_gallery_requests', [item['key'] for item in items])

    @override_settings(VISUAL_SEARCH_PRIVATE_ACCESS_REQUESTS_ENABLED=True)
    def test_nav_enabled_and_active(self):
        groups = _workspace_nav('private_gallery_requests')
        items = [item for group in groups for item in group['items']]
        inbox = next(item for item in items if item['key'] == 'private_gallery_requests')
        self.assertTrue(inbox['active'])
        self.assertEqual(inbox['url'], reverse('photographer_workspace:private_gallery_requests'))
