from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import AdministrativeRegion, ClientProfile, Country, PhotographerProfile, PhotographerSpecialty, PhotographerWebsiteProfile
from apps.photographers.forms import PhotographerSpecialtiesForm

User = get_user_model()


def make_user(**kwargs):
    password = kwargs.pop("password", "TestPass123!")
    kwargs.setdefault("account_status", User.AccountStatus.ACTIVE)
    kwargs.setdefault("email_verified", True)
    return User.objects.create_user(password=password, **kwargs)


@override_settings(MEDIA_ROOT="/tmp/lumispixel-test-media")
class PhotographerOnboardingTests(TestCase):
    def setUp(self):
        self.user = make_user(email="photo@example.com", primary_role=User.PrimaryRole.PHOTOGRAPHER, last_active_workspace=User.Workspace.PHOTOGRAPHER)
        self.profile = PhotographerProfile.objects.create(user=self.user, slug="photo")
        self.client_user = make_user(email="client@example.com", primary_role=User.PrimaryRole.CLIENT)
        ClientProfile.objects.create(user=self.client_user)
        self.wedding = PhotographerSpecialty.objects.get(slug="wedding")
        self.sports = PhotographerSpecialty.objects.get(slug="sports")
        self.country = Country.objects.create(source_id=233, name="United States", iso2="US", iso3="USA")
        self.region = AdministrativeRegion.objects.create(source_id=1456, country=self.country, name="California", code="US-CA", region_type="state")

    def test_anonymous_user_redirects_to_login(self):
        response = self.client.get(reverse("photographers:setup-dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_client_is_redirected_from_photographer_onboarding(self):
        self.client.force_login(self.client_user)
        response = self.client.get(reverse("photographers:setup-dashboard"))
        self.assertRedirects(response, reverse("clients:setup-dashboard"), fetch_redirect_response=False)

    def test_photographer_can_access_all_steps(self):
        self.client.force_login(self.user)
        for name in (
            "photographers:onboarding-welcome",
            "photographers:onboarding-profile",
            "photographers:onboarding-specialties",
            "photographers:onboarding-business",
            "photographers:onboarding-theme",
        ):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)

    def test_profile_uses_scrollable_native_location_selects(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("photographers:onboarding-profile"))

        self.assertContains(response, "data-location-country")
        self.assertContains(response, "data-location-region")
        self.assertContains(response, "js/location_selects.")

    def test_profile_step_saves_user_profile_and_uploads(self):
        self.client.force_login(self.user)
        image = SimpleUploadedFile("avatar.gif", b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;", content_type="image/gif")
        logo = SimpleUploadedFile("logo.gif", image.read(), content_type="image/gif")
        image.seek(0)
        response = self.client.post(reverse("photographers:onboarding-profile"), {
            "first_name": "Pat", "last_name": "Pixel", "display_name": "Pat Pixel", "business_name": "Lumis Studio", "phone_number": "+1 555 1212", "website": "https://example.com", "country_record": self.country.pk, "administrative_region": self.region.pk, "city": "Oakland", "timezone": "America/Los_Angeles", "profile_photo": image, "business_logo": logo,
        })
        self.assertRedirects(response, reverse("photographers:onboarding-specialties"), fetch_redirect_response=False)
        self.user.refresh_from_db(); self.profile.refresh_from_db()
        self.assertEqual(self.user.first_name, "Pat")
        self.assertEqual(self.profile.display_name, "Pat Pixel")
        self.assertEqual(self.profile.country, "United States")
        self.assertEqual(self.profile.state, "California")
        self.assertEqual(self.profile.country_record, self.country)
        self.assertEqual(self.profile.administrative_region, self.region)
        self.assertTrue(self.profile.profile_photo)
        self.assertTrue(self.profile.business_logo)

    def test_specialties_form_lists_other_last(self):
        form = PhotographerSpecialtiesForm(instance=self.profile)

        self.assertEqual(form.fields["specialties"].queryset.last().slug, "other")

    def test_specialties_business_and_theme_save_and_reload(self):
        self.client.force_login(self.user)
        self.client.post(reverse("photographers:onboarding-specialties"), {"specialties": [self.wedding.pk, self.sports.pk]})
        self.assertEqual(set(self.profile.specialties.values_list("slug", flat=True)), {"wedding", "sports"})
        self.client.post(reverse("photographers:onboarding-business"), {"business_type": PhotographerProfile.BusinessType.STUDIO, "years_of_experience": 7, "travel_radius": "50", "willing_to_travel": "on", "destination_photographer": "on", "available_nationally": "on", "available_internationally": "on", "default_currency": "usd", "instagram_url": "https://instagram.com/lumis", "facebook_url": "", "tiktok_url": "", "linkedin_url": "", "youtube_url": ""})
        self.client.post(reverse("photographers:onboarding-theme"), {"website_theme": PhotographerProfile.WebsiteTheme.BASIC, "action": "finish_setup"})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.business_type, PhotographerProfile.BusinessType.STUDIO)
        self.assertEqual(self.profile.default_currency, "USD")
        self.assertTrue(self.profile.willing_to_travel)
        self.assertEqual(self.profile.travel_radius, 50)
        self.assertTrue(self.profile.destination_photographer)
        self.assertTrue(self.profile.available_nationally)
        self.assertTrue(self.profile.available_internationally)
        self.assertEqual(self.profile.website_theme, PhotographerProfile.WebsiteTheme.BASIC)
        self.assertTrue(self.profile.onboarding_completed)
        self.assertRedirects(self.client.get(reverse("photographers:onboarding-theme")), reverse("photographer_workspace:dashboard"), fetch_redirect_response=False)


    def test_business_step_clears_travel_coverage_when_not_willing_to_travel(self):
        self.profile.service_area = "Legacy Bay Area"
        self.profile.travel_radius = 100
        self.profile.destination_photographer = True
        self.profile.available_nationally = True
        self.profile.available_internationally = True
        self.profile.onboarding_step = 4
        self.profile.save()
        self.client.force_login(self.user)

        response = self.client.post(reverse("photographers:onboarding-business"), {
            "business_type": PhotographerProfile.BusinessType.INDIVIDUAL,
            "years_of_experience": 4,
            "default_currency": "usd",
            "travel_radius": "100",
            "instagram_url": "https://instagram.com/lumis",
            "facebook_url": "https://facebook.com/lumis",
            "tiktok_url": "https://tiktok.com/@lumis",
            "linkedin_url": "https://linkedin.com/company/lumis",
            "youtube_url": "https://youtube.com/@lumis",
        })

        self.assertRedirects(response, reverse("photographers:onboarding-theme"), fetch_redirect_response=False)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.willing_to_travel)
        self.assertIsNone(self.profile.travel_radius)
        self.assertFalse(self.profile.destination_photographer)
        self.assertFalse(self.profile.available_nationally)
        self.assertFalse(self.profile.available_internationally)
        self.assertEqual(self.profile.service_area, "Legacy Bay Area")
        self.assertEqual(self.profile.instagram_url, "https://instagram.com/lumis")
        self.assertEqual(self.profile.facebook_url, "https://facebook.com/lumis")
        self.assertEqual(self.profile.tiktok_url, "https://tiktok.com/@lumis")
        self.assertEqual(self.profile.linkedin_url, "https://linkedin.com/company/lumis")
        self.assertEqual(self.profile.youtube_url, "https://youtube.com/@lumis")

    def test_business_step_requires_radius_or_broad_availability_when_traveling(self):
        self.profile.onboarding_step = 4
        self.profile.save(update_fields=["onboarding_step", "updated_at"])
        self.client.force_login(self.user)

        response = self.client.post(reverse("photographers:onboarding-business"), {
            "business_type": PhotographerProfile.BusinessType.STUDIO,
            "years_of_experience": 7,
            "willing_to_travel": "on",
            "default_currency": "usd",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a travel radius or indicate national/international availability.")
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.onboarding_step, 4)

    def test_broad_or_destination_availability_implies_willing_to_travel(self):
        self.client.force_login(self.user)
        for field in ("available_nationally", "available_internationally", "destination_photographer"):
            with self.subTest(field=field):
                self.profile.willing_to_travel = False
                self.profile.travel_radius = None
                self.profile.available_nationally = False
                self.profile.available_internationally = False
                self.profile.destination_photographer = False
                self.profile.save()

                payload = {
                    "business_type": PhotographerProfile.BusinessType.STUDIO,
                    "years_of_experience": 7,
                    "default_currency": "usd",
                    field: "on",
                }
                if field == "destination_photographer":
                    payload["travel_radius"] = "25"
                response = self.client.post(reverse("photographers:onboarding-business"), payload)

                self.assertRedirects(response, reverse("photographers:onboarding-theme"), fetch_redirect_response=False)
                self.profile.refresh_from_db()
                self.assertTrue(self.profile.willing_to_travel)
                self.assertTrue(getattr(self.profile, field))

    def test_business_step_location_summary_and_edit_link(self):
        self.profile.city = "Oakland"
        self.profile.state = "CA"
        self.profile.country = "United States"
        self.profile.save()
        self.client.force_login(self.user)

        response = self.client.get(reverse("photographers:onboarding-business"))

        self.assertContains(response, "Primary business location:")
        self.assertContains(response, "Oakland, CA, United States")
        self.assertContains(response, reverse("photographers:onboarding-profile"))
        self.assertContains(response, "lumis-onboarding__business-grid")
        self.assertContains(response, "lumis-onboarding-choice lumis-onboarding-choice--business")
        self.assertContains(response, "data-travel-toggle")
        self.assertContains(response, "<option value=\"10\">10 miles</option>", html=True)
        self.assertContains(response, "<option value=\"250\">250 miles</option>", html=True)
        self.assertNotContains(response, "control.disabled")

    def test_business_step_incomplete_location_summary(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("photographers:onboarding-business"))

        self.assertContains(response, "Primary business location not completed.")

    def test_validation_errors_are_inline(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("photographers:onboarding-profile"), {"first_name": "", "last_name": "", "website": "not-a-url"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "lumis-onboarding__error")

    def test_finished_photographer_redirects_from_all_onboarding_steps(self):
        self.profile.onboarding_completed = True
        self.profile.save(update_fields=["onboarding_completed", "updated_at"])
        self.client.force_login(self.user)

        for name in (
            "photographers:onboarding-welcome",
            "photographers:onboarding-profile",
            "photographers:onboarding-specialties",
            "photographers:onboarding-business",
            "photographers:onboarding-theme",
        ):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertRedirects(response, reverse("photographer_workspace:dashboard"), fetch_redirect_response=False)

    def test_client_profile_is_not_created_for_photographer_routing(self):
        PhotographerProfile.objects.filter(user=self.user).delete()
        self.client.force_login(self.user)

        response = self.client.get(reverse("accounts:post-login-redirect"))

        self.assertRedirects(response, reverse("photographers:setup-dashboard"), fetch_redirect_response=False)
        self.assertTrue(PhotographerProfile.objects.filter(user=self.user).exists())
        self.assertFalse(ClientProfile.objects.filter(user=self.user).exists())


class PhotographerThemeExperienceTests(TestCase):
    def setUp(self):
        self.user = make_user(email="theme-photo@example.com", primary_role=User.PrimaryRole.PHOTOGRAPHER, last_active_workspace=User.Workspace.PHOTOGRAPHER)
        self.profile = PhotographerProfile.objects.create(user=self.user, slug="theme-photo", onboarding_step=5)
        self.client.force_login(self.user)

    def test_all_six_theme_cards_and_config_panels_render(self):
        response = self.client.get(reverse("photographers:onboarding-theme"))
        for label in ("Frame", "Narrative", "Panorama", "Monograph", "Collective", "Atelier"):
            self.assertContains(response, label)
        self.assertContains(response, "Choose and arrange sections")
        for source in (
            "kimono_main/dark/index-21.html",
            "kimono_main/dark/index-19.html",
            "kimono_main/dark/index-15.html",
            "kimono_main/dark/index-5.html",
        ):
            self.assertNotContains(response, source)
        self.assertContains(response, "project_0_title")
        self.assertContains(response, "lumis-onboarding__theme-grid")

    def test_preview_urls_resolve_and_do_not_change_theme(self):
        self.profile.website_theme = PhotographerProfile.WebsiteTheme.BASIC
        self.profile.save()
        names = (
            "photographers:photographer_onboarding_theme_preview_basic",
            "photographers:photographer_onboarding_theme_preview_elegant",
            "photographers:photographer_onboarding_theme_preview_modern_studio",
            "photographers:photographer_onboarding_theme_preview_cinematic",
            "photographers:photographer_onboarding_theme_preview_portfolio_editorial",
            "photographers:photographer_onboarding_theme_preview_sports_events",
        )
        for name in names:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Completed preview")
            self.assertContains(response, "img/lumis_favicon_v1")
            self.assertContains(response, "css/showcase_portfolio")
            self.assertTemplateUsed(response, "photographers/theme_previews/showcase.html")
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.website_theme, PhotographerProfile.WebsiteTheme.BASIC)

    def test_completed_collective_preview_includes_team_section(self):
        response = self.client.get(reverse("photographers:theme-preview", args=["collective"]))

        self.assertContains(response, "The people behind the work")
        self.assertContains(response, '<div class="showcase-team__grid">')
        self.assertContains(response, "Associate Photographer")
        self.assertContains(response, "Elias Morgan")
        self.assertContains(response, "css/showcase_team")
        self.assertContains(response, "Verified client")
        self.assertNotContains(response, "kimono_main/dark/index-5.html")

    def test_frame_preview_restores_six_slide_carousel(self):
        response = self.client.get(reverse("photographers:theme-preview", args=["frame"]))

        self.assertContains(response, "data-frame-carousel")
        self.assertContains(response, "data-frame-slide", count=6)
        self.assertContains(response, "data-frame-dot=", count=6)
        self.assertContains(response, "data-frame-previous")
        self.assertContains(response, "data-frame-next")
        self.assertContains(response, "js/theme_showcase")

    def test_non_frame_preview_keeps_static_hero(self):
        response = self.client.get(reverse("photographers:theme-preview", args=["narrative"]))

        self.assertNotContains(response, "data-frame-carousel")
        self.assertContains(response, "css/showcase_portfolio")

    def test_services_preview_uses_six_card_index_five_composition(self):
        response = self.client.get(reverse("photographers:theme-preview", args=["narrative"]))

        self.assertContains(response, "wptb-services pb-4")
        self.assertContains(response, '<article class="showcase-service-card', count=6)
        self.assertContains(response, "Wedding Photography")
        self.assertContains(response, "Brand Photography")
        self.assertContains(response, "css/showcase_services")
        self.assertNotContains(response, "is-highlighted")

    def test_reviews_preview_uses_index_nineteen_testimonial_composition(self):
        response = self.client.get(reverse("photographers:theme-preview", args=["narrative"]))

        self.assertContains(response, "wptb-testimonial-one testimonial-colored bg-image")
        self.assertContains(response, "data-review-slide", count=3)
        self.assertContains(response, "data-review-previous")
        self.assertContains(response, "data-review-next")
        self.assertContains(response, "4.9")
        self.assertContains(response, "Based on 128 verified reviews")
        self.assertContains(response, "css/showcase_reviews")
        self.assertContains(response, "js/showcase_reviews")
        self.assertContains(response, "data-review-excerpt", count=3)
        self.assertContains(response, "data-review-more", count=3)
        self.assertContains(response, "data-review-modal")
        self.assertContains(response, "data-review-modal-copy")

    def test_selected_sections_render_in_custom_preview_without_saving(self):
        response = self.client.post(reverse("photographers:selected-theme-preview"), {
            "website_theme": PhotographerProfile.WebsiteTheme.ELEGANT,
            "website_sections": ["hero", "portfolio", "team", "reviews", "contact"],
            "section_order": "hero,team,portfolio,reviews,contact",
            "preview_context": "onboarding",
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your selected preview — Narrative")
        self.assertContains(response, "Back to customize")
        self.assertContains(response, 'id="team"')
        self.assertContains(response, 'id="reviews"')
        content = response.content.decode()
        self.assertLess(content.index('id="team"'), content.index('id="portfolio"'))
        self.assertLess(content.index('id="portfolio"'), content.index('id="reviews"'))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.website_theme, PhotographerProfile.WebsiteTheme.BASIC)
        self.assertFalse(self.profile.website_profile.sections.exists())

    def test_custom_preview_selection_is_restored_on_return(self):
        self.client.post(reverse("photographers:selected-theme-preview"), {
            "website_theme": PhotographerProfile.WebsiteTheme.PORTFOLIO_EDITORIAL,
            "website_sections": ["hero", "team", "about", "contact"],
            "section_order": "hero,about,team,contact",
        })

        response = self.client.get(f'{reverse("photographers:onboarding-theme")}?restore_preview=1')

        self.assertEqual(response.context["form"]["website_theme"].value(), PhotographerProfile.WebsiteTheme.PORTFOLIO_EDITORIAL)
        self.assertEqual(response.context["form"]["section_order"].value(), "hero,about,team,contact")
        self.assertEqual(set(response.context["selected_sections"]), {"hero", "about", "team", "contact"})

    def test_custom_preview_requires_a_valid_theme(self):
        response = self.client.post(reverse("photographers:selected-theme-preview"), {
            "website_theme": "unknown-theme",
            "website_sections": ["hero", "contact"],
        })

        self.assertRedirects(response, reverse("photographers:onboarding-theme"), fetch_redirect_response=False)
        self.assertNotIn("photographer_selected_theme_preview", self.client.session)

    def test_section_selection_and_order_are_saved_without_deleting_content(self):
        payload = {
            "website_theme": PhotographerProfile.WebsiteTheme.BASIC,
            "website_sections": ["hero", "portfolio", "team", "contact"],
            "section_order": "hero,team,portfolio,contact",
            "action": "finish_setup",
        }
        response = self.client.post(reverse("photographers:onboarding-theme"), payload)

        self.assertRedirects(response, reverse("photographer_workspace:dashboard"), fetch_redirect_response=False)
        website = self.profile.website_profile
        self.assertEqual(list(website.sections.filter(is_enabled=True).values_list("section_type", flat=True)), ["hero", "team", "portfolio", "contact"])
        team = website.sections.get(section_type="team")
        team.content = {"heading": "Our people"}
        team.save(update_fields=["content", "updated_at"])

        self.profile.onboarding_completed = False
        self.profile.save(update_fields=["onboarding_completed", "updated_at"])
        self.client.post(reverse("photographers:onboarding-theme"), {
            "website_theme": PhotographerProfile.WebsiteTheme.ELEGANT,
            "website_sections": ["hero", "about", "contact"],
            "section_order": "hero,about,contact",
            "hero_heading": "Soft light",
            "action": "save_draft",
        })
        team.refresh_from_db()
        self.assertFalse(team.is_enabled)
        self.assertEqual(team.content, {"heading": "Our people"})

    def test_completed_photographer_can_return_to_builder_and_add_team(self):
        self.profile.onboarding_completed = True
        self.profile.save(update_fields=["onboarding_completed", "updated_at"])

        response = self.client.get(reverse("photographers:website-builder"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Build Your Photographer Website")
        self.assertEqual(self.client.get(reverse("photographers:theme-preview", args=["frame"])).status_code, 200)
        response = self.client.post(reverse("photographers:website-builder"), {
            "website_theme": PhotographerProfile.WebsiteTheme.BASIC,
            "website_sections": ["hero", "portfolio", "team", "contact"],
            "section_order": "hero,portfolio,team,contact",
            "action": "save_website",
        })

        self.assertRedirects(response, reverse("photographers:website-builder"), fetch_redirect_response=False)
        self.assertTrue(self.profile.website_profile.sections.get(section_type="team").is_enabled)

    def test_elegant_finish_requires_fields_but_draft_preserves_partial(self):
        response = self.client.post(reverse("photographers:onboarding-theme"), {"website_theme": PhotographerProfile.WebsiteTheme.ELEGANT, "hero_heading": "Soft light", "action": "save_draft"})
        self.assertRedirects(response, reverse("photographers:setup-dashboard"), fetch_redirect_response=False)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.onboarding_completed)
        self.assertEqual(self.profile.website_theme, PhotographerProfile.WebsiteTheme.ELEGANT)
        self.assertEqual(self.profile.website_profile.theme_content["hero_heading"], "Soft light")
        response = self.client.post(reverse("photographers:onboarding-theme"), {"website_theme": PhotographerProfile.WebsiteTheme.ELEGANT, "action": "finish_setup"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")

    def test_basic_completes_without_extra_fields(self):
        response = self.client.post(reverse("photographers:onboarding-theme"), {"website_theme": PhotographerProfile.WebsiteTheme.BASIC, "action": "finish_setup"})
        self.assertRedirects(response, reverse("photographer_workspace:dashboard"), fetch_redirect_response=False)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.onboarding_completed)

    def test_portfolio_projects_save(self):
        payload = {"website_theme": PhotographerProfile.WebsiteTheme.PORTFOLIO_EDITORIAL, "editorial_heading": "Editorial", "artist_statement": "Statement", "project_section_heading": "Projects", "contact_statement": "Contact", "project_0_title": "Project A", "project_0_description": "Desc", "action": "finish_setup"}
        response = self.client.post(reverse("photographers:onboarding-theme"), payload)
        self.assertRedirects(response, reverse("photographer_workspace:dashboard"), fetch_redirect_response=False)
        self.assertEqual(self.profile.website_profile.projects.count(), 1)

    def test_anonymous_and_client_preview_access(self):
        self.client.logout()
        response = self.client.get(reverse("photographers:photographer_onboarding_theme_preview_basic"))
        self.assertEqual(response.status_code, 302)
        client_user = make_user(email="theme-client@example.com", primary_role=User.PrimaryRole.CLIENT)
        ClientProfile.objects.create(user=client_user)
        self.client.force_login(client_user)
        response = self.client.get(reverse("photographers:photographer_onboarding_theme_preview_basic"))
        self.assertRedirects(response, reverse("clients:setup-dashboard"), fetch_redirect_response=False)

    def test_invalid_upload_rejected(self):
        bad = SimpleUploadedFile("bad.txt", b"bad", content_type="text/plain")
        response = self.client.post(reverse("photographers:onboarding-theme"), {"website_theme": PhotographerProfile.WebsiteTheme.BASIC, "action": "save_draft", "hero_image": bad})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload a valid image")


class PhotographerWebsitesPublicPageTests(TestCase):
    def test_photographer_websites_public_page_renders(self):
        response = self.client.get(reverse("photographers:websites"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "photographer_websites.html")
        self.assertContains(response, "Photographer Websites")
        self.assertContains(response, "your work feels")
        self.assertContains(response, "dpw-canvas")
        self.assertContains(response, "Start Building")
        self.assertContains(response, reverse("accounts:get-started"))
