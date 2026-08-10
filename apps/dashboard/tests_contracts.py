import hashlib
from unittest.mock import patch

from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.contracts import create_contract_from_template
from apps.clients.contract_pdfs import generate_signed_contract_pdf
from apps.clients.models import (Client, ClientSession, Contract, ContractEvent, ContractSignature,
                                 ContractTemplate, SignedContractDocument)
from apps.dashboard.models import StudioMembership
from apps.clients.contracts import render_merge_fields


class ContractWorkflowTests(TestCase):
    def make_studio(self, email):
        user = User.objects.create_user(email=email, password="pass12345")
        user.account_status = User.AccountStatus.ACTIVE
        user.primary_role = User.PrimaryRole.PHOTOGRAPHER
        user.save()
        studio = PhotographerProfile.objects.create(user=user, onboarding_completed=True)
        client = Client.objects.create(photographer=studio, first_name="Maya", last_name="Cole")
        booking = ClientSession.objects.create(
            photographer=studio, client=client, session_type="Portrait",
            starts_at=timezone.now() + timezone.timedelta(days=5),
        )
        template = ContractTemplate.objects.create(
            photographer=studio, name="Portrait standard", title="Portrait Agreement",
            content="Original persisted terms", created_by=user,
        )
        return user, studio, client, booking, template

    def setUp(self):
        self.owner, self.studio, self.crm_client, self.booking, self.template = self.make_studio(
            "contract-owner@example.com"
        )

    def test_template_and_contract_snapshot_are_persisted(self):
        contract = create_contract_from_template(
            booking=self.booking, template=self.template, actor=self.owner,
        )
        self.assertEqual(contract.client, self.booking.client)
        self.assertEqual(contract.photographer, self.studio)
        self.assertEqual(contract.status, Contract.Status.DRAFT)
        self.assertEqual(contract.content, "Original persisted terms")
        self.assertEqual(contract.version, self.template.version)
        self.assertTrue(Contract.objects.filter(pk=contract.pk).exists())
        self.assertTrue(contract.events.filter(event_type=ContractEvent.EventType.CREATED).exists())

        self.template.content = "Updated future terms"
        self.template.version = 2
        self.template.save()
        contract.refresh_from_db()
        self.assertEqual(contract.content, "Original persisted terms")
        self.assertEqual(contract.version, 1)

    def test_contract_relationship_validation_rejects_mismatches(self):
        _other_owner, other_studio, other_client, _other_booking, other_template = self.make_studio(
            "validation-other@example.com"
        )
        contract = Contract(
            photographer=self.studio, booking=self.booking, client=other_client,
            template=other_template, title="Invalid", content="Terms",
        )
        with self.assertRaises(ValidationError) as error:
            contract.full_clean()
        self.assertIn("client", error.exception.message_dict)
        self.assertIn("template", error.exception.message_dict)
        self.assertNotEqual(other_studio, self.studio)

    def test_owner_creates_draft_from_booking_and_can_reopen_it(self):
        self.client.force_login(self.owner)
        create_url = reverse("photographer_workspace:contract_create", args=[self.booking.pk])
        response = self.client.post(create_url, {"template": self.template.pk})
        contract = Contract.objects.get()
        self.assertRedirects(response, reverse("photographer_workspace:contract_detail", args=[contract.pk]))
        detail = self.client.get(response.url)
        self.assertContains(detail, "Portrait Agreement")
        self.assertContains(detail, "Original persisted terms")
        booking_page = self.client.get(
            reverse("photographer_workspace:booking_detail", args=[self.booking.pk]), {"tab": "contract"},
        )
        self.assertContains(booking_page, "Draft")
        self.assertContains(booking_page, reverse("photographer_workspace:contract_detail", args=[contract.pk]))

    def test_create_page_shows_persisted_booking_context_and_selectable_templates(self):
        self.booking.location = "North Studio"
        self.booking.booking_value = "425.00"
        self.booking.save(update_fields=["location", "booking_value"])
        self.template.description = "A persisted portrait agreement"
        self.template.save(update_fields=["description"])
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("photographer_workspace:contract_create", args=[self.booking.pk])
        )

        self.assertContains(response, "Booking Summary")
        self.assertContains(response, "Maya Cole")
        self.assertContains(response, "Portrait")
        self.assertContains(response, "North Studio")
        self.assertContains(response, "425.00")
        self.assertContains(response, "Select Template")
        self.assertContains(response, "Customize")
        self.assertContains(response, "Preview")
        self.assertContains(response, "Send")
        self.assertContains(response, "A persisted portrait agreement")
        self.assertContains(response, f'name="template" value="{self.template.pk}"')
        self.assertContains(response, "Continue to Customize")
        self.assertContains(response, "Manage Templates")

    def test_create_page_empty_state_links_to_new_template_and_booking(self):
        self.template.is_active = False
        self.template.save(update_fields=["is_active"])
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("photographer_workspace:contract_create", args=[self.booking.pk])
        )

        self.assertContains(response, "No contract templates yet")
        self.assertContains(response, "Create Contract Template")
        self.assertContains(
            response, reverse("photographer_workspace:contract_template_create")
        )
        self.assertContains(
            response, reverse("photographer_workspace:booking_detail", args=[self.booking.pk])
        )
        self.assertNotContains(response, f'name="template" value="{self.template.pk}"')

    def test_duplicate_create_submission_reuses_the_active_draft(self):
        self.client.force_login(self.owner)
        create_url = reverse("photographer_workspace:contract_create", args=[self.booking.pk])
        first = self.client.post(create_url, {"template": self.template.pk})
        second = self.client.post(create_url, {"template": self.template.pk})

        self.assertEqual(first.url, second.url)
        self.assertEqual(Contract.objects.count(), 1)
        contract = Contract.objects.get()
        self.assertEqual(contract.events.filter(event_type=ContractEvent.EventType.CREATED).count(), 1)

    def test_cross_workspace_booking_template_and_contract_ids_are_hidden(self):
        other_owner, _other_studio, _other_client, other_booking, other_template = self.make_studio(
            "contract-other@example.com"
        )
        private_contract = create_contract_from_template(
            booking=other_booking, template=other_template, actor=other_owner,
        )
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.get(reverse("photographer_workspace:contract_create", args=[other_booking.pk])).status_code,
            404,
        )
        response = self.client.post(
            reverse("photographer_workspace:contract_create", args=[self.booking.pk]),
            {"template": other_template.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        self.assertEqual(Contract.objects.filter(photographer=self.studio).count(), 0)
        self.assertEqual(
            self.client.get(reverse("photographer_workspace:contract_detail", args=[private_contract.pk])).status_code,
            404,
        )

    def test_manager_and_assigned_photographer_can_access_but_unassigned_cannot(self):
        manager = User.objects.create_user(email="manager-contract@example.com", password="pass12345")
        photographer = User.objects.create_user(email="assigned-contract@example.com", password="pass12345")
        unassigned = User.objects.create_user(email="unassigned-contract@example.com", password="pass12345")
        for user in (manager, photographer, unassigned):
            user.account_status = User.AccountStatus.ACTIVE
            user.save()
        StudioMembership.objects.create(
            studio=self.studio, user=manager, role=StudioMembership.Role.MANAGER,
            status=StudioMembership.Status.ACTIVE,
        )
        assigned_membership = StudioMembership.objects.create(
            studio=self.studio, user=photographer, role=StudioMembership.Role.PHOTOGRAPHER,
            status=StudioMembership.Status.ACTIVE,
        )
        StudioMembership.objects.create(
            studio=self.studio, user=unassigned, role=StudioMembership.Role.PHOTOGRAPHER,
            status=StudioMembership.Status.ACTIVE,
        )
        self.booking.assigned_members.add(assigned_membership)
        url = reverse("photographer_workspace:contract_create", args=[self.booking.pk])
        for user in (manager, photographer):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(unassigned)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_anonymous_user_is_redirected_to_login(self):
        url = reverse("photographer_workspace:contract_create", args=[self.booking.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_merge_fields_render_real_values_and_unknown_fields_survive(self):
        self.crm_client.email = "maya@example.com"
        self.crm_client.save(update_fields=["email"])
        self.booking.location = "City Studio"
        self.booking.booking_value = "425.00"
        self.booking.save(update_fields=["location", "booking_value"])
        content = "Hello {{ client.full_name }} at {{ booking.location }} — {{ unknown.value }}"
        rendered = render_merge_fields(content, self.booking)
        self.assertIn("Maya Cole", rendered)
        self.assertIn("City Studio", rendered)
        self.assertIn("{{ unknown.value }}", rendered)

    def test_template_crud_validation_archive_duplicate_and_tenant_isolation(self):
        self.client.force_login(self.owner)
        list_url = reverse("photographer_workspace:contract_templates")
        create_url = reverse("photographer_workspace:contract_template_create")
        self.assertContains(self.client.get(list_url), "Portrait standard")
        invalid = self.client.post(create_url, {
            "name": "Invalid", "title": "Invalid", "category": "general",
            "content": "Hello {{ client.secret }}", "is_active": "on",
        })
        self.assertContains(invalid, "Unsupported merge field")
        created = self.client.post(create_url, {
            "name": "Wedding", "title": "Wedding terms", "category": "wedding",
            "description": "Ceremony agreement", "content": "Hello {{ client.first_name }}",
            "is_active": "on",
        })
        self.assertRedirects(created, list_url)
        item = ContractTemplate.objects.get(name="Wedding")
        edit = self.client.post(reverse("photographer_workspace:contract_template_edit", args=[item.pk]), {
            "name": "Wedding revised", "title": "Wedding terms", "category": "wedding",
            "description": "Updated", "content": "Hello {{ client.full_name }}", "is_active": "on",
        })
        self.assertRedirects(edit, list_url)
        item.refresh_from_db()
        self.assertEqual(item.version, 2)
        self.client.post(reverse("photographer_workspace:contract_template_action", args=[item.pk]), {"action": "duplicate"})
        self.assertTrue(ContractTemplate.objects.filter(photographer=self.studio, name__contains="(copy)").exists())
        self.client.post(reverse("photographer_workspace:contract_template_action", args=[item.pk]), {"action": "toggle_active"})
        item.refresh_from_db()
        self.assertFalse(item.is_active)
        create_page = self.client.get(reverse("photographer_workspace:contract_create", args=[self.booking.pk]))
        self.assertNotContains(create_page, f'<option value="{item.pk}">', html=True)
        other_owner, _studio, _client, _booking, other_template = self.make_studio("template-private@example.com")
        other_template.name = "Private other workspace template"
        other_template.save(update_fields=["name"])
        self.assertNotContains(self.client.get(list_url), other_template.name)
        self.assertEqual(self.client.get(reverse("photographer_workspace:contract_template_edit", args=[other_template.pk])).status_code, 404)

    def test_template_form_renders_authoring_layout_with_supported_merge_fields(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("photographer_workspace:contract_template_create"))

        self.assertContains(response, "Template Details")
        self.assertContains(response, "Contract Content")
        self.assertContains(response, "Merge Fields")
        self.assertContains(response, "Template Tips")
        self.assertContains(response, "Start writing your contract terms here...")
        self.assertContains(response, 'class="lp-container lp-container--wide lp-contract-template-editor"', html=False)
        self.assertContains(response, ">Photographer Workspace</a>", html=False)
        self.assertContains(response, "<span>Settings</span>", html=False)
        self.assertNotContains(response, "lp-contract-template-back", html=False)
        self.assertContains(response, 'class="lp-contract-document"', html=False)
        self.assertContains(response, 'role="toolbar"', html=False)
        self.assertContains(response, 'role="group" aria-label="Editing history"', html=False)
        self.assertContains(response, 'data-editor-command="undo"', html=False)
        self.assertContains(response, 'data-editor-command="redo"', html=False)
        self.assertContains(response, 'id="id_description"', html=False)
        self.assertNotContains(response, "Internal description Optional")
        self.assertContains(response, 'class="lp-contract-template-status__control"', html=False)
        self.assertContains(response, "This template is available when creating contracts.")
        self.assertContains(response, "Preview")
        self.assertContains(response, "data-template-preview", html=False)
        self.assertContains(response, "data-preview-dialog", html=False)
        self.assertContains(response, "Add contract content to see its preview here.")
        self.assertContains(response, 'form="contract-template-form"', html=False)
        self.assertContains(response, 'data-merge-insert="{{ client.full_name }}"', html=False)
        self.assertContains(response, 'data-merge-insert="{{ booking.date }}"', html=False)
        self.assertNotContains(response, "data-merge-copy", html=False)
        self.assertContains(response, "Search merge fields...")
        self.assertContains(response, 'data-merge-search-text="client.full_name Client full name"', html=False)
        self.assertNotContains(response, "Save Draft")

    def test_draft_customization_persists_without_changing_template(self):
        contract = create_contract_from_template(booking=self.booking, template=self.template, actor=self.owner)
        self.client.force_login(self.owner)
        url = reverse("photographer_workspace:contract_customize", args=[contract.pk])
        response = self.client.post(url, {"title": "Personal terms", "content": "Customized persisted terms", "action": "save"})
        self.assertRedirects(response, url)
        contract.refresh_from_db()
        self.template.refresh_from_db()
        self.assertEqual(contract.content, "Customized persisted terms")
        self.assertEqual(self.template.content, "Original persisted terms")
        self.assertEqual(
            contract.events.filter(event_type=ContractEvent.EventType.CUSTOMIZED).count(), 1,
        )
        self.client.logout()
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(url), "Customized persisted terms")

    def test_template_management_requires_settings_permission(self):
        manager = User.objects.create_user(email="template-manager@example.com", password="pass12345")
        manager.account_status = User.AccountStatus.ACTIVE
        manager.save()
        StudioMembership.objects.create(studio=self.studio, user=manager, role=StudioMembership.Role.MANAGER,
                                        status=StudioMembership.Status.ACTIVE)
        self.client.force_login(manager)
        self.assertEqual(self.client.get(reverse("photographer_workspace:contract_templates")).status_code, 403)

    def _draft_with_email(self):
        self.crm_client.email = "maya@example.com"
        self.crm_client.save(update_fields=["email"])
        return create_contract_from_template(booking=self.booking, template=self.template, actor=self.owner)

    def test_preview_renders_resolved_snapshot_safely(self):
        self.template.content = "Hello {{ client.full_name }} <script>alert(1)</script>"
        self.template.save(update_fields=["content"])
        contract = create_contract_from_template(booking=self.booking, template=self.template, actor=self.owner)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("photographer_workspace:contract_preview", args=[contract.pk]))
        self.assertContains(response, "Hello Maya Cole")
        self.assertNotContains(response, "<script>alert(1)</script>", html=True)
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "Contract Content")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_send_secure_review_view_and_resend(self):
        contract = self._draft_with_email()
        self.client.force_login(self.owner)
        send_url = reverse("photographer_workspace:contract_send", args=[contract.pk])
        self.client.post(send_url)
        contract.refresh_from_db()
        self.assertEqual(contract.status, Contract.Status.SENT)
        self.assertEqual(contract.send_count, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(len(contract.review_token_digest), 64)
        token = mail.outbox[0].body.split("/client/contracts/review/")[1].split("/")[0]
        review = self.client.get(reverse("clients:contract-review", args=[token]))
        self.assertContains(review, "Original persisted terms")
        self.assertNotContains(review, "Photographer Workspace")
        contract.refresh_from_db()
        first_viewed_at = contract.viewed_at
        self.assertEqual(contract.status, Contract.Status.VIEWED)
        self.client.get(reverse("clients:contract-review", args=[token]))
        contract.refresh_from_db()
        self.assertEqual(contract.viewed_at, first_viewed_at)
        self.assertEqual(contract.events.filter(event_type=ContractEvent.EventType.VIEWED).count(), 1)

        self.client.force_login(self.owner)
        self.client.post(send_url)
        contract.refresh_from_db()
        self.assertEqual(Contract.objects.filter(pk=contract.pk).count(), 1)
        self.assertEqual(contract.send_count, 2)
        self.assertEqual(contract.events.filter(event_type=ContractEvent.EventType.RESENT).count(), 1)
        self.assertEqual(self.client.get(reverse("clients:contract-review", args=[token])).status_code, 404)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_missing_and_invalid_email_are_not_sent(self):
        contract = create_contract_from_template(booking=self.booking, template=self.template, actor=self.owner)
        self.client.force_login(self.owner)
        url = reverse("photographer_workspace:contract_send", args=[contract.pk])
        self.client.post(url)
        self.crm_client.email = "not-an-email"
        self.crm_client.save(update_fields=["email"])
        self.client.post(url)
        contract.refresh_from_db()
        self.assertEqual(contract.status, Contract.Status.DRAFT)
        self.assertEqual(contract.send_count, 0)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_invalid_expired_and_revoked_tokens_are_hidden(self):
        contract = self._draft_with_email()
        self.client.force_login(self.owner)
        self.client.post(reverse("photographer_workspace:contract_send", args=[contract.pk]))
        token = mail.outbox[0].body.split("/client/contracts/review/")[1].split("/")[0]
        self.assertEqual(self.client.get(reverse("clients:contract-review", args=["invalid-token"])).status_code, 404)
        contract.review_token_expires_at = timezone.now() - timezone.timedelta(seconds=1)
        contract.save(update_fields=["review_token_expires_at"])
        self.assertEqual(self.client.get(reverse("clients:contract-review", args=[token])).status_code, 404)
        contract.review_token_expires_at = timezone.now() + timezone.timedelta(days=1)
        contract.review_token_revoked_at = timezone.now()
        contract.save(update_fields=["review_token_expires_at", "review_token_revoked_at"])
        self.assertEqual(self.client.get(reverse("clients:contract-review", args=[token])).status_code, 404)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_cross_tenant_preview_and_send_are_hidden(self):
        other_owner, _studio, other_client, other_booking, other_template = self.make_studio("send-other@example.com")
        other_client.email = "private@example.com"
        other_client.save(update_fields=["email"])
        contract = create_contract_from_template(booking=other_booking, template=other_template, actor=other_owner)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse("photographer_workspace:contract_preview", args=[contract.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("photographer_workspace:contract_send", args=[contract.pk])).status_code, 404)
        self.assertEqual(len(mail.outbox), 0)

    def test_email_failure_leaves_contract_draft_and_without_token(self):
        contract = self._draft_with_email()
        self.client.force_login(self.owner)
        with patch("apps.clients.contracts.EmailMultiAlternatives.send", side_effect=OSError("mail down")):
            response = self.client.post(reverse("photographer_workspace:contract_send", args=[contract.pk]), follow=True)
        contract.refresh_from_db()
        self.assertContains(response, "was not marked as sent")
        self.assertEqual(contract.status, Contract.Status.DRAFT)
        self.assertEqual(contract.review_token_digest, "")
        self.assertEqual(contract.send_count, 0)
        self.assertFalse(contract.events.filter(event_type=ContractEvent.EventType.SENT).exists())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_client_signs_with_persisted_evidence_and_refreshes_success(self):
        contract = self._draft_with_email()
        self.client.force_login(self.owner)
        self.client.post(reverse("photographer_workspace:contract_send", args=[contract.pk]))
        token = mail.outbox[0].body.split("/client/contracts/review/")[1].split("/")[0]
        self.client.logout()
        url = reverse("clients:contract-review", args=[token])
        response = self.client.post(url, {
            "signer_name": "Maya Cole", "signature_value": "Maya Cole",
            "consent_accepted": "on",
        }, REMOTE_ADDR="192.0.2.10", HTTP_USER_AGENT="Test browser")
        self.assertContains(response, "Contract signed successfully")
        contract.refresh_from_db()
        evidence = ContractSignature.objects.get(contract=contract)
        self.assertEqual(contract.status, Contract.Status.SIGNED)
        self.assertEqual(contract.signed_at, evidence.signed_at)
        self.assertEqual(evidence.content_hash, hashlib.sha256(contract.rendered_content.encode()).hexdigest())
        self.assertEqual(evidence.client, self.crm_client)
        self.assertEqual(evidence.photographer, self.studio)
        self.assertTrue(evidence.consent_accepted)
        self.assertEqual(evidence.ip_address, "192.0.2.10")
        self.assertContains(self.client.get(url), "Contract signed successfully")
        self.assertEqual(contract.events.filter(event_type=ContractEvent.EventType.SIGNED).count(), 1)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_signature_requires_name_signature_and_consent(self):
        contract = self._draft_with_email()
        self.client.force_login(self.owner)
        self.client.post(reverse("photographer_workspace:contract_send", args=[contract.pk]))
        token = mail.outbox[0].body.split("/client/contracts/review/")[1].split("/")[0]
        self.client.logout()
        response = self.client.post(reverse("clients:contract-review", args=[token]), {
            "signer_name": "", "signature_value": "",
        })
        self.assertContains(response, "This field is required", count=3)
        contract.refresh_from_db()
        self.assertEqual(contract.status, Contract.Status.VIEWED)
        self.assertFalse(ContractSignature.objects.filter(contract=contract).exists())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_double_sign_invalid_token_and_atomic_failure_create_no_extra_evidence(self):
        contract = self._draft_with_email()
        self.client.force_login(self.owner)
        self.client.post(reverse("photographer_workspace:contract_send", args=[contract.pk]))
        token = mail.outbox[0].body.split("/client/contracts/review/")[1].split("/")[0]
        self.client.logout()
        payload = {"signer_name": "Maya Cole", "signature_value": "Maya Cole", "consent_accepted": "on"}
        url = reverse("clients:contract-review", args=[token])
        self.client.post(url, payload)
        second = self.client.post(url, payload)
        self.assertContains(second, "Contract signed successfully")
        self.assertEqual(ContractSignature.objects.filter(contract=contract).count(), 1)
        self.assertEqual(self.client.post(reverse("clients:contract-review", args=["invalid"]), payload).status_code, 404)

        other = self._draft_with_email()
        self.client.force_login(self.owner)
        self.client.post(reverse("photographer_workspace:contract_send", args=[other.pk]))
        other_token = mail.outbox[-1].body.split("/client/contracts/review/")[1].split("/")[0]
        self.client.logout()
        with patch("apps.clients.contracts.ContractEvent.objects.create", side_effect=RuntimeError("audit failure")):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse("clients:contract-review", args=[other_token]), payload)
        other.refresh_from_db()
        self.assertNotEqual(other.status, Contract.Status.SIGNED)
        self.assertFalse(ContractSignature.objects.filter(contract=other).exists())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_signed_contract_is_locked_and_cross_workspace_cannot_retrieve_it(self):
        contract = self._draft_with_email()
        self.client.force_login(self.owner)
        self.client.post(reverse("photographer_workspace:contract_send", args=[contract.pk]))
        token = mail.outbox[0].body.split("/client/contracts/review/")[1].split("/")[0]
        self.client.logout()
        self.client.post(reverse("clients:contract-review", args=[token]), {
            "signer_name": "Maya Cole", "signature_value": "Maya Cole", "consent_accepted": "on",
        })
        contract.refresh_from_db()
        contract.content = "Changed after signature"
        with self.assertRaises(ValidationError):
            contract.save()
        evidence = contract.signature
        evidence.signer_name = "Someone else"
        with self.assertRaises(ValidationError):
            evidence.save()
        event = contract.events.get(event_type=ContractEvent.EventType.SIGNED)
        event.metadata = {"tampered": True}
        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            event.delete()

        protected_changes = {
            "title": "Changed title",
            "template": None,
            "booking": self.booking,
            "client": self.crm_client,
        }
        for field, value in protected_changes.items():
            pristine = Contract.objects.get(pk=contract.pk)
            setattr(pristine, field, value)
            if getattr(pristine, field) == getattr(contract, field):
                # Exercise reassignment using a valid same-tenant alternative.
                if field == "booking":
                    value = ClientSession.objects.create(
                        photographer=self.studio, client=self.crm_client,
                        session_type="Alternative", starts_at=timezone.now(),
                    )
                elif field == "client":
                    value = Client.objects.create(
                        photographer=self.studio, first_name="Other", last_name="Client",
                    )
                setattr(pristine, field, value)
            with self.assertRaises(ValidationError, msg=f"signed {field} must be immutable"):
                pristine.save()

        other_owner, _studio, _client, _booking, _template = self.make_studio("signature-other@example.com")
        self.client.force_login(other_owner)
        self.assertEqual(self.client.get(reverse("photographer_workspace:contract_detail", args=[contract.pk])).status_code, 404)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_signed_pdf_uses_snapshot_and_is_available_to_both_parties(self):
        contract = self._draft_with_email()
        self.client.force_login(self.owner)
        self.client.post(reverse("photographer_workspace:contract_send", args=[contract.pk]))
        token = mail.outbox[0].body.split("/client/contracts/review/")[1].split("/")[0]
        self.client.logout()
        self.client.post(reverse("clients:contract-review", args=[token]), {
            "signer_name": "Maya Cole", "signature_value": "Maya Cole", "consent_accepted": "on",
        })
        contract.refresh_from_db()
        document = contract.signed_document
        self.addCleanup(document.file.delete, False)
        self.assertEqual(document.status, SignedContractDocument.Status.READY)
        self.assertEqual(document.signed_content_hash, contract.signature.content_hash)
        self.assertEqual(document.file_size, document.file.size)
        self.assertTrue(document.file.name.startswith(f"contracts/{self.studio.pk}/{contract.pk}/"))
        with document.file.open("rb") as generated:
            original_pdf = generated.read()
        self.assertTrue(original_pdf.startswith(b"%PDF-1.4"))
        self.assertIn(b"Original persisted terms", original_pdf)
        self.assertIn(b"Maya Cole", original_pdf)

        client_view = self.client.get(reverse("clients:signed-contract-pdf", args=[token]))
        self.assertEqual(client_view.status_code, 200)
        self.assertEqual(client_view["Cache-Control"], "private, no-store")
        self.assertEqual(self.client.get(reverse("clients:signed-contract-pdf", args=["guessed-key"])).status_code, 404)

        self.template.content = "Mutated template terms"
        self.template.save(update_fields=["content"])
        self.booking.location = "A changed location"
        self.booking.save(update_fields=["location"])
        regenerated = generate_signed_contract_pdf(contract.pk)
        with regenerated.file.open("rb") as stored:
            self.assertEqual(stored.read(), original_pdf)
        self.assertEqual(
            contract.events.filter(event_type=ContractEvent.EventType.PDF_GENERATED).count(), 1,
        )

        self.client.force_login(self.owner)
        workspace_download = self.client.get(
            reverse("photographer_workspace:signed_contract_pdf_download", args=[contract.pk]),
        )
        self.assertEqual(workspace_download.status_code, 200)
        self.assertIn("attachment", workspace_download["Content-Disposition"])
        other_owner, _studio, _client, _booking, _template = self.make_studio("pdf-other@example.com")
        self.client.force_login(other_owner)
        self.assertEqual(self.client.get(
            reverse("photographer_workspace:signed_contract_pdf", args=[contract.pk])
        ).status_code, 404)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_pdf_failure_preserves_signature_and_can_regenerate(self):
        contract = self._draft_with_email()
        self.client.force_login(self.owner)
        self.client.post(reverse("photographer_workspace:contract_send", args=[contract.pk]))
        token = mail.outbox[0].body.split("/client/contracts/review/")[1].split("/")[0]
        self.client.logout()
        with patch("apps.clients.contract_pdfs.render_signed_contract_pdf", side_effect=RuntimeError("renderer down")):
            self.client.post(reverse("clients:contract-review", args=[token]), {
                "signer_name": "Maya Cole", "signature_value": "Maya Cole", "consent_accepted": "on",
            })
        contract.refresh_from_db()
        self.assertEqual(contract.status, Contract.Status.SIGNED)
        self.assertEqual(contract.signed_document.status, SignedContractDocument.Status.FAILED)
        document = generate_signed_contract_pdf(contract.pk)
        self.addCleanup(document.file.delete, False)
        self.assertEqual(document.status, SignedContractDocument.Status.READY)
        self.assertEqual(document.signed_content_hash, contract.signature.content_hash)
