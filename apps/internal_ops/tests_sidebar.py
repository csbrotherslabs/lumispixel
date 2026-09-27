from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class InternalSidebarShellTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            email="sidebar-admin@lumispixel.test",
            password="Pass1234!",
        )
        self.client.force_login(self.user)

    def test_internal_shell_includes_responsive_sidebar_controls(self):
        response = self.client.get(reverse("internal_ops:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="internalSidebar"')
        self.assertContains(response, "data-sidebar-toggle", count=2)
        self.assertContains(response, "data-sidebar-close", count=2)
        self.assertContains(response, "internal_sidebar.css")
        self.assertContains(response, "internal_sidebar.js")

    def test_sidebar_brand_uses_colored_lumis_mark(self):
        response = self.client.get(reverse("internal_ops:dashboard"))
        self.assertContains(response, "lumis_favicon_v2.png")
        self.assertContains(response, 'class="li-brand__word">LUMIS</span>')
        self.assertContains(response, 'class="li-brand__pill">Internal</span>')

    def test_employee_navigation_remains_available_in_sidebar(self):
        response = self.client.get(reverse("internal_ops:dashboard"))
        self.assertContains(response, reverse("internal_ops:employees"))
        self.assertContains(response, "Employees")
