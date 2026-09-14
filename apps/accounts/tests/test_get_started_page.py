from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class GetStartedPageTests(TestCase):
    def test_get_started_renders_new_choice_cards_for_anonymous_user(self):
        response = self.client.get(reverse("accounts:get-started"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "What would you like to do?")
        self.assertContains(response, "I’m a photographer")
        self.assertContains(response, "I’m here for my photos")
        self.assertContains(response, "I need a photographer")
        self.assertContains(response, "audience-photographers.webp")
        self.assertContains(response, "audience-clients.webp")
        self.assertContains(response, "audience-hire-photographer.webp")

    def test_get_started_keeps_authenticated_account_context(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(email="get-started@example.com", password="test-password-123")
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:get-started"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your existing access stays connected.")
        self.assertNotContains(response, "Already have an account?")
