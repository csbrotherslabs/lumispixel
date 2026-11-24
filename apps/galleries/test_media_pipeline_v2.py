from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from PIL import Image

from .derivatives import derivative_name, generate_photo_derivatives
from .models import GalleryPhoto, GalleryStorageDeletion
from .signals import queue_gallery_derivatives
from .storage_cleanup import enqueue_storage_deletions


ORIGINAL = "galleries/1/2/originals/example.jpg"


class MemoryStorage:
    def __init__(self, original):
        self.objects = {ORIGINAL: original}
        self.types = {}
        self.writes = []
        self.fail_preview = False

    def exists(self, name):
        return name in self.objects

    def open(self, name, mode):
        return BytesIO(self.objects[name])

    def save(self, name, content):
        if self.fail_preview and "/preview/" in name:
            raise OSError("simulated storage failure")
        self.objects[name] = content.read()
        self.types[name] = content.content_type
        self.writes.append(name)
        return name


class DerivativeTests(SimpleTestCase):
    def setUp(self):
        source = BytesIO()
        Image.new("RGB", (1200, 1800), "blue").save(source, "JPEG")
        self.original = source.getvalue()
        self.storage = MemoryStorage(self.original)
        self.photo = SimpleNamespace(
            file=SimpleNamespace(name=ORIGINAL),
            status=GalleryPhoto.Status.COMPLETED,
            Status=GalleryPhoto.Status,
        )

    def test_paths(self):
        self.assertEqual(derivative_name(ORIGINAL, "thumbnail"),
                         "galleries/1/2/variants/thumbnail/example.webp")
        for path in ("other/1/2/originals/example.jpg",
                     "galleries/1/../originals/example.jpg",
                     "/galleries/1/2/originals/example.jpg"):
            with self.assertRaises(ValueError):
                derivative_name(path, "thumbnail")
        with self.assertRaises(ValueError):
            derivative_name(ORIGINAL, "original")

    def test_generation_and_duplicate_execution(self):
        with patch("apps.galleries.derivatives.gallery_photo_storage",
                   return_value=self.storage):
            self.assertTrue(generate_photo_derivatives(self.photo))
            self.assertTrue(generate_photo_derivatives(self.photo))
        self.assertEqual(len(self.storage.writes), 2)
        self.assertEqual(self.storage.objects[ORIGINAL], self.original)
        for variant, size in (("thumbnail", (640, 960)),
                              ("preview", (1200, 1800))):
            name = derivative_name(ORIGINAL, variant)
            self.assertEqual(self.storage.types[name], "image/webp")
            with Image.open(BytesIO(self.storage.objects[name])) as image:
                self.assertEqual(image.format, "WEBP")
                self.assertEqual(image.size, size)
                image.verify()

    def test_partial_failure_retry(self):
        with patch("apps.galleries.derivatives.gallery_photo_storage",
                   return_value=self.storage):
            self.storage.fail_preview = True
            with self.assertRaises(OSError):
                generate_photo_derivatives(self.photo)
            self.storage.fail_preview = False
            self.assertTrue(generate_photo_derivatives(self.photo))
        self.assertEqual(self.storage.writes, [
            derivative_name(ORIGINAL, "thumbnail"),
            derivative_name(ORIGINAL, "preview"),
        ])

    def test_exif_orientation(self):
        source = BytesIO()
        image = Image.new("RGB", (1200, 600))
        exif = image.getexif()
        exif[274] = 6
        image.save(source, "JPEG", exif=exif)
        self.storage.objects[ORIGINAL] = source.getvalue()
        with patch("apps.galleries.derivatives.gallery_photo_storage",
                   return_value=self.storage):
            generate_photo_derivatives(self.photo)
        with Image.open(BytesIO(self.storage.objects[
                derivative_name(ORIGINAL, "thumbnail")])) as result:
            self.assertEqual(result.size, (480, 960))


class SchedulingTests(SimpleTestCase):
    def test_completed_upload_queues_after_commit(self):
        photo = SimpleNamespace(pk=42, file=ORIGINAL,
                                status=GalleryPhoto.Status.COMPLETED)
        with patch("apps.galleries.signals.transaction.on_commit") as commit, \
                patch("apps.galleries.tasks.generate_gallery_photo_derivatives.delay") as delay:
            queue_gallery_derivatives(GalleryPhoto, photo, created=True)
            delay.assert_not_called()
            callback = commit.call_args.args[0]
            self.assertTrue(commit.call_args.kwargs["robust"])
            callback()
            delay.assert_called_once_with(42)

    def test_raw_and_unrelated_updates_do_not_queue(self):
        photo = SimpleNamespace(pk=42, file=ORIGINAL,
                                status=GalleryPhoto.Status.COMPLETED)
        with patch("apps.galleries.signals.transaction.on_commit") as commit:
            queue_gallery_derivatives(GalleryPhoto, photo, raw=True)
            queue_gallery_derivatives(GalleryPhoto, photo, created=False,
                                      update_fields={"caption"})
            commit.assert_not_called()

    def test_b2_cleanup_includes_both_derivatives(self):
        key = "private/dev/" + ORIGINAL
        with patch.object(GalleryStorageDeletion.objects, "bulk_create"):
            rows = enqueue_storage_deletions([{
                "storage_backend": GalleryStorageDeletion.Backend.B2,
                "object_key": key,
            }])
        self.assertEqual({row.object_key for row in rows}, {
            key,
            "private/dev/" + derivative_name(ORIGINAL, "thumbnail"),
            "private/dev/" + derivative_name(ORIGINAL, "preview"),
        })
