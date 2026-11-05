"""Existing visual-search history must survive later gallery migrations."""
from types import SimpleNamespace
from unittest.mock import patch
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.test import SimpleTestCase


class VisualSearchMigrationDependencyTests(SimpleTestCase):
    def test_visual_dependencies_are_stable_gallery_photo_schema(self):
        loader = MigrationLoader(None)
        for name in ['0001_initial', '0007_face_deletion_review']:
            migration = loader.disk_migrations['visual_search', name]
            self.assertIn(('galleries', '0002_galleryphoto'), migration.dependencies)
            self.assertNotIn(('galleries', '__latest__'), migration.dependencies)

    def test_pre_cover_database_history_can_apply_new_gallery_fields(self):
        loader = MigrationLoader(None)
        # Simulate the previous database: visual-search migrations already exist,
        # but the newly introduced cover/density fields are not applied yet.
        applied = set(loader.graph.forwards_plan(('galleries', '0036_studio_photo_comments')))
        applied.update(loader.graph.forwards_plan(('visual_search', '0007_face_deletion_review')))
        applied = {node for node in applied if node[0] != 'galleries' or node[1] <= '0036_studio_photo_comments'}
        with patch.object(MigrationRecorder, 'applied_migrations', return_value=applied):
            loader.check_consistent_history(SimpleNamespace(alias='upgrade_test'))
        plan = loader.graph.forwards_plan(('galleries', '0038_watermark_density'))
        pending = [node for node in plan if node not in applied]
        self.assertEqual(pending, [('galleries', '0037_gallery_cover_position'),
                                   ('galleries', '0038_watermark_density')])
