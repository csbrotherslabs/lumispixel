from types import SimpleNamespace
from unittest.mock import patch

from django.template import Context, Engine
from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.core.templatetags.social_preview import social_preview


@override_settings(ALLOWED_HOSTS=["testserver"], STATIC_URL="/static/")
class SocialPreviewResilienceTests(SimpleTestCase):
    def test_error_template_without_request_renders(self):
        engine = Engine(libraries={
            "social_preview": "apps.core.templatetags.social_preview",
        })
        template = engine.from_string(
            "{% load social_preview %}{% social_preview as social %}"
            "{{ social.title }}|{{ social.image }}|{{ social.url }}"
        )
        with patch("apps.core.templatetags.social_preview.static") as static:
            self.assertEqual(
                template.render(Context()),
                "LumisPixel — Create. Deliver. Grow.||",
            )
        static.assert_not_called()

    def test_missing_manifest_entry_does_not_break_page(self):
        request = RequestFactory().get("/", secure=True)
        with patch("apps.core.templatetags.social_preview.reverse", return_value="/"), patch(
            "apps.core.templatetags.social_preview.static",
            side_effect=ValueError("Missing staticfiles manifest entry"),
        ):
            result = social_preview({"request": request})
        self.assertEqual(result["image"], "")
        self.assertEqual(result["url"], "https://testserver/")

    def test_gallery_cover_survives_missing_static_fallback(self):
        request = RequestFactory().get("/g/example/", secure=True)
        gallery = SimpleNamespace(
            name="Wedding", public_id="example",
            cover_image=SimpleNamespace(url="/media/cover.jpg"),
        )
        with patch("apps.core.templatetags.social_preview.reverse", return_value="/g/example/"), patch(
            "apps.core.templatetags.social_preview.static",
            side_effect=ValueError("Missing staticfiles manifest entry"),
        ):
            result = social_preview({"request": request}, gallery)
        self.assertEqual(result["image"], "https://testserver/media/cover.jpg")
