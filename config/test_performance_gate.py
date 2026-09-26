"""Fast performance regression gate for CI.

The gate aggregates the contracts that protect LumisPixel's highest-volume
gallery paths. These tests also remain part of normal Django discovery.
"""

from apps.galleries.test_large_gallery_performance import LargeGalleryPaginationTests
from apps.galleries.test_query_efficiency import ClientGalleryQueryEfficiencyTests
from apps.galleries.test_upload_memory_performance import UploadMemoryPerformanceTests
from apps.galleries.test_media_delivery_performance import GalleryMediaDeliveryPerformanceTests


__all__ = [
    "LargeGalleryPaginationTests",
    "ClientGalleryQueryEfficiencyTests",
    "UploadMemoryPerformanceTests",
    "GalleryMediaDeliveryPerformanceTests",
]
