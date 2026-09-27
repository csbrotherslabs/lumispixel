from django.test import SimpleTestCase

from apps.internal_ops.models import SupportTicket

from .support_forms import SupportTicketIntakeForm


class HelpCenterSupportFormTests(SimpleTestCase):
    def test_category_dropdown_exposes_all_support_ticket_categories(self):
        form = SupportTicketIntakeForm()
        choices = list(form.fields["category"].choices)

        self.assertEqual(choices[0], ("", "Choose an issue category"))
        self.assertEqual(choices[1:], list(SupportTicket.Category.choices))
        self.assertEqual(len(choices) - 1, 10)

    def test_category_dropdown_contains_expected_labels(self):
        form = SupportTicketIntakeForm()
        labels = [label for value, label in form.fields["category"].choices if value]

        self.assertEqual(
            labels,
            [
                "Account & access",
                "Billing & plan",
                "Galleries & delivery",
                "AI tools",
                "Editing & culling",
                "Photographer website",
                "Bookings & calendar",
                "Client access",
                "Technical issue",
                "Other",
            ],
        )

    def test_invalid_category_is_rejected(self):
        form = SupportTicketIntakeForm(
            data={
                "category": "not-a-category",
                "subject": "Need help",
                "description": "Something happened while using LumisPixel.",
                "related_url": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("category", form.errors)
