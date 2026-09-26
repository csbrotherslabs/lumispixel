from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.dashboard.invitation_actions import resend_pending_invitation, revoke_pending_invitation


class InvitationActionScopingTests(SimpleTestCase):
    @patch("apps.dashboard.invitation_actions.get_object_or_404")
    @patch("apps.dashboard.invitation_actions.resend_studio_invitation")
    @patch("apps.dashboard.invitation_actions.record")
    def test_resend_lookup_is_studio_scoped(self, _record, _resend, get_mock):
        membership = Mock(invitation_sent_at=None)
        get_mock.return_value = membership
        request = Mock()
        studio = Mock()

        resend_pending_invitation(request, studio, 42)

        lookup = get_mock.call_args.kwargs
        self.assertEqual(lookup["pk"], 42)
        self.assertIs(lookup["studio"], studio)

    @patch("apps.dashboard.invitation_actions.get_object_or_404")
    @patch("apps.dashboard.invitation_actions.record")
    def test_revoke_clears_credential(self, _record, get_mock):
        membership = Mock()
        get_mock.return_value = membership

        revoke_pending_invitation(Mock(), Mock(), 7)

        self.assertEqual(membership.invitation_token_digest, "")
        membership.save.assert_called_once()
