from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from apps.internal_ops.models import EmployeeProfile
from apps.internal_ops.employee_services import send_employee_invitation, EmployeeInvitationError
from apps.notifications.lifecycle import eligible
from apps.notifications.payload_crypto import decrypt_payload


@override_settings(PUBLIC_BASE_URL="https://lumispixel.example", EMAIL_PAYLOAD_KEYS=Fernet.generate_key().decode())
class EmployeeInvitationLifecycleTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="employee@example.com", password="test-password-123")
        self.user.email_verified = True
        self.user.save(update_fields=["email_verified"])
        self.employee = EmployeeProfile.objects.create(user=self.user, employee_id="EMP-TEST", status=EmployeeProfile.Status.ACTIVE)

    def test_invitation_encrypted_and_suspension_blocks_dispatch(self):
        row = send_employee_invitation(None, self.employee)
        self.assertEqual(row.plain_body, "")
        self.assertIn("https://lumispixel.example", decrypt_payload(row)[1])
        self.assertTrue(eligible(row))
        self.employee.status = EmployeeProfile.Status.SUSPENDED
        self.employee.save(update_fields=["status"])
        self.assertFalse(eligible(row))
        with self.assertRaises(EmployeeInvitationError):
            send_employee_invitation(None, self.employee)

    def test_resend_supersedes_pending_login_notice(self):
        first = send_employee_invitation(None, self.employee)
        second = send_employee_invitation(None, self.employee)
        first.refresh_from_db()
        self.assertEqual(first.status, "cancelled")
        self.assertEqual(second.status, "pending")
