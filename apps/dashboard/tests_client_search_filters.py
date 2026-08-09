from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientInvoice, ClientSession


class ClientSearchFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="owner@example.com", password="pass12345",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            last_active_workspace=User.Workspace.PHOTOGRAPHER,
            email_verified=True, account_status=User.AccountStatus.ACTIVE,
        )
        cls.studio = PhotographerProfile.objects.create(
            user=cls.user, slug="search-studio", onboarding_completed=True,
        )
        other_user = User.objects.create_user(
            email="other@example.com", password="pass12345",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            last_active_workspace=User.Workspace.PHOTOGRAPHER,
            email_verified=True, account_status=User.AccountStatus.ACTIVE,
        )
        cls.other_studio = PhotographerProfile.objects.create(
            user=other_user, slug="other-search-studio", onboarding_completed=True,
        )
        cls.avery = Client.objects.create(
            photographer=cls.studio, first_name="Avery", last_name="O'Neil-Smith",
            email="Avery@Example.com", phone="+1 503-555-0199", company="North-Star Co",
            status=Client.Status.ACTIVE, client_type=Client.ClientType.BUSINESS,
            tags=["VIP", "Wedding"],
        )
        cls.blair = Client.objects.create(
            photographer=cls.studio, first_name="Blair", last_name="Jones",
            email="blair@example.net", status=Client.Status.INACTIVE,
            client_type=Client.ClientType.INDIVIDUAL, tags=["Portrait"],
        )
        Client.objects.create(
            photographer=cls.other_studio, first_name="Private", last_name="Identity",
            email="secret@elsewhere.example", tags=["Secret"],
        )
        ClientSession.objects.create(
            photographer=cls.studio, client=cls.avery, session_type="Wedding",
            starts_at=timezone.now() + timezone.timedelta(days=2),
            status=ClientSession.Status.CONFIRMED,
        )
        ClientInvoice.objects.create(
            photographer=cls.studio, client=cls.avery, total="500", amount_paid="100",
            status=ClientInvoice.Status.SENT,
        )
        for number in range(13):
            Client.objects.create(
                photographer=cls.studio, first_name=f"Paged{number:02}", last_name="Person",
                status=Client.Status.ACTIVE, client_type=Client.ClientType.INDIVIDUAL,
            )

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse("photographer_workspace:clients")

    def assert_names(self, params, included=(), excluded=()):
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 200)
        for name in included:
            self.assertContains(response, name)
        for name in excluded:
            self.assertNotContains(response, name)
        return response

    def test_searches_advertised_persisted_fields_and_handles_input_edges(self):
        for query in ("Avery", "o'neil-smith", "  aVeRy O'NeIl  ", "avery@example",
                      "503-555", "north-star", "O'Neil-"):
            self.assert_names({"q": query}, ["Avery O&#x27;Neil-Smith"], ["Blair Jones"])
        response = self.assert_names({"q": "%_[]"}, excluded=["Avery O&#x27;Neil-Smith", "Blair Jones"])
        self.assertContains(response, "No clients match your filters")

    def test_search_and_tag_are_tenant_scoped(self):
        self.assert_names({"q": "secret@elsewhere.example"}, excluded=["Private Identity"])
        self.assert_names({"tag": "Secret"}, excluded=["Private Identity", "Avery O&#x27;Neil-Smith"])
        self.assert_names({"tag": "vip"}, ["Avery O&#x27;Neil-Smith"], ["Blair Jones"])

    def test_each_filter_and_combination(self):
        cases = [
            ({"status": "inactive"}, "Blair Jones", "Avery O&#x27;Neil-Smith"),
            ({"client_type": "business"}, "Avery O&#x27;Neil-Smith", "Blair Jones"),
            ({"upcoming": "yes"}, "Avery O&#x27;Neil-Smith", "Blair Jones"),
            ({"upcoming": "no", "q": "Blair"}, "Blair Jones", "Avery O&#x27;Neil-Smith"),
            ({"balance": "yes"}, "Avery O&#x27;Neil-Smith", "Blair Jones"),
            ({"balance": "no", "status": "inactive"}, "Blair Jones", "Avery O&#x27;Neil-Smith"),
            ({"q": "Avery", "status": "active", "tag": "VIP"}, "Avery O&#x27;Neil-Smith", "Blair Jones"),
        ]
        for params, included, excluded in cases:
            self.assert_names(params, [included], [excluded])

    def test_invalid_values_are_safe_and_unknown_tag_matches_nothing(self):
        self.assert_names({"status": "not-a-status", "client_type": "nope"},
                          ["Avery O&#x27;Neil-Smith", "Blair Jones"])
        self.assert_names({"tag": "does-not-exist"},
                          excluded=["Avery O&#x27;Neil-Smith", "Blair Jones"])
        response = self.client.get(self.url, {"q": "x" * 500})
        self.assertEqual(len(response.context["client_query"]), 200)

    def test_pagination_retains_search_and_filters_and_recovers_invalid_page(self):
        second = self.client.get(self.url, {"status": "active", "page": 2})
        self.assertEqual(second.context["client_page"].number, 2)
        self.assertContains(second, "status=active&amp;page=1")
        narrowed = self.client.get(self.url, {"q": "Avery", "status": "active", "page": 99})
        self.assertEqual(narrowed.context["client_page"].number, 1)
        self.assertEqual(narrowed.context["client_page"].paginator.count, 1)
