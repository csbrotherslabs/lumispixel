from django.test import TestCase

from apps.accounts.models import PhotographerProfile, User
from apps.ai_engine.models import AIJob, AIProcessingStatus
from apps.billing.ai_usage import AIUsageLimitExceeded, get_usage_balance
from apps.billing.models import AIUsageTransaction
from apps.galleries.models import Gallery


class AIProcessingUsageIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="ai-processing-ledger@example.com",
            password="strong-test-password",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
        )
        self.photographer = PhotographerProfile.objects.create(
            user=self.user,
            display_name="Ledger Processing Studio",
            onboarding_completed=True,
        )
        self.gallery = Gallery.objects.create(
            photographer=self.photographer,
            name="AI Gallery",
            slug="ai-gallery",
            image_count=10,
        )

    def make_job(self, *, task_type=AIJob.TaskType.BLUR_DETECTION, image_count=None):
        if image_count is not None:
            self.gallery.image_count = image_count
            self.gallery.save(update_fields=["image_count", "updated_at"])
        job = AIJob.objects.create(
            photographer=self.photographer,
            gallery=self.gallery,
            task_type=task_type,
        )
        AIProcessingStatus.objects.create(job=job, total_images=self.gallery.image_count)
        return job

    def test_running_job_reserves_one_action_per_image(self):
        job = self.make_job()

        job.status = AIJob.Status.RUNNING
        job.save(update_fields=["status", "updated_at"])
        job.refresh_from_db()

        self.assertEqual(job.attempts, 1)
        self.assertIsNotNone(job.usage_reservation_id)
        self.assertEqual(job.usage_reservation.kind, AIUsageTransaction.Kind.RESERVE)
        self.assertEqual(job.usage_reservation.total_units, 10)
        self.assertEqual(job.usage_reservation.operation.code, AIJob.TaskType.BLUR_DETECTION)

        balance = get_usage_balance(self.photographer)
        self.assertEqual(balance.included_reserved, 10)
        self.assertEqual(balance.included_consumed, 0)
        self.assertEqual(balance.included_remaining, 90)

    def test_completed_job_settles_reserved_usage(self):
        job = self.make_job()
        job.status = AIJob.Status.RUNNING
        job.save()
        progress = job.progress
        progress.completed_images = 10
        progress.save(update_fields=["completed_images", "updated_at"])

        job.status = AIJob.Status.COMPLETED
        job.save(update_fields=["status", "updated_at"])

        balance = get_usage_balance(self.photographer)
        self.assertEqual(balance.included_reserved, 0)
        self.assertEqual(balance.included_consumed, 10)
        self.assertEqual(balance.included_remaining, 90)
        self.assertTrue(
            AIUsageTransaction.objects.filter(
                related_transaction=job.usage_reservation,
                kind=AIUsageTransaction.Kind.SETTLE,
                included_units=10,
            ).exists()
        )

    def test_partial_completion_settles_completed_images_and_releases_remainder(self):
        job = self.make_job()
        job.status = AIJob.Status.RUNNING
        job.save()
        progress = job.progress
        progress.completed_images = 7
        progress.failed_images = 3
        progress.save(update_fields=["completed_images", "failed_images", "updated_at"])

        job.status = AIJob.Status.COMPLETED
        job.save()

        balance = get_usage_balance(self.photographer)
        self.assertEqual(balance.included_consumed, 7)
        self.assertEqual(balance.included_reserved, 0)
        self.assertEqual(balance.included_remaining, 93)
        self.assertTrue(
            AIUsageTransaction.objects.filter(
                related_transaction=job.usage_reservation,
                kind=AIUsageTransaction.Kind.RELEASE,
                included_units=3,
            ).exists()
        )

    def test_failed_job_releases_full_reservation(self):
        job = self.make_job()
        job.status = AIJob.Status.RUNNING
        job.save()
        reservation_id = job.usage_reservation_id

        job.status = AIJob.Status.FAILED
        job.save()

        balance = get_usage_balance(self.photographer)
        self.assertEqual(balance.included_reserved, 0)
        self.assertEqual(balance.included_consumed, 0)
        self.assertEqual(balance.included_remaining, 100)
        self.assertTrue(
            AIUsageTransaction.objects.filter(
                related_transaction_id=reservation_id,
                kind=AIUsageTransaction.Kind.RELEASE,
                included_units=10,
            ).exists()
        )

    def test_cancelled_running_job_releases_reservation(self):
        job = self.make_job()
        job.status = AIJob.Status.RUNNING
        job.save()

        job.status = AIJob.Status.CANCELLED
        job.save()

        balance = get_usage_balance(self.photographer)
        self.assertEqual(balance.included_reserved, 0)
        self.assertEqual(balance.included_remaining, 100)

    def test_retry_gets_new_attempt_scoped_reservation(self):
        job = self.make_job()
        job.status = AIJob.Status.RUNNING
        job.save()
        first_reservation_id = job.usage_reservation_id
        job.status = AIJob.Status.FAILED
        job.save()

        job.status = AIJob.Status.QUEUED
        job.save()
        job.status = AIJob.Status.RUNNING
        job.save()
        job.refresh_from_db()

        self.assertEqual(job.attempts, 2)
        self.assertNotEqual(job.usage_reservation_id, first_reservation_id)
        self.assertEqual(job.usage_reservation.total_units, 10)
        balance = get_usage_balance(self.photographer)
        self.assertEqual(balance.included_reserved, 10)
        self.assertEqual(balance.included_remaining, 90)

    def test_job_cannot_start_when_allowance_is_insufficient(self):
        job = self.make_job(image_count=101)
        job.status = AIJob.Status.RUNNING

        with self.assertRaises(AIUsageLimitExceeded):
            job.save()

        job.refresh_from_db()
        self.assertEqual(job.status, AIJob.Status.QUEUED)
        self.assertEqual(job.attempts, 0)
        self.assertIsNone(job.usage_reservation_id)
        balance = get_usage_balance(self.photographer)
        self.assertEqual(balance.included_reserved, 0)
        self.assertEqual(balance.included_remaining, 100)

    def test_empty_gallery_job_does_not_charge_usage(self):
        job = self.make_job(image_count=0)
        job.status = AIJob.Status.RUNNING
        job.save()
        job.refresh_from_db()

        self.assertEqual(job.attempts, 1)
        self.assertIsNone(job.usage_reservation_id)
        balance = get_usage_balance(self.photographer)
        self.assertEqual(balance.included_reserved, 0)
        self.assertEqual(balance.included_consumed, 0)
