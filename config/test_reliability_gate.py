"""Fast reliability gate for CI.

This module deliberately aggregates the targeted reliability contracts so CI
can fail early before the full Django suite. The underlying tests remain in
their domain modules and still run in the complete suite.
"""

from config.test_celery_reliability import CeleryReliabilityContractTests
from config.test_external_retry_strategy import ExternalRetryContractTests
from config.test_reliability_failure_isolation import SupportFailureIsolationTests
from apps.galleries.test_idempotency import MultipartCompletionIdempotencyTests
from apps.galleries.test_recovery_degraded import RecoveryAndDegradedBehaviorTests
from apps.galleries.test_storage_cleanup import GalleryStorageDeletionTests


# Imports are intentionally the gate: Django's test discovery executes these
# TestCase classes when CI targets config.test_reliability_gate.
__all__ = [
    "CeleryReliabilityContractTests",
    "ExternalRetryContractTests",
    "SupportFailureIsolationTests",
    "MultipartCompletionIdempotencyTests",
    "RecoveryAndDegradedBehaviorTests",
    "GalleryStorageDeletionTests",
]
