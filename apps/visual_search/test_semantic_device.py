"""Unit tests for semantic CLIP device selection; no model downloads required."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.visual_search.semantic import _load_model


class SemanticDeviceTests(SimpleTestCase):
    def tearDown(self):
        _load_model.cache_clear()

    def _fake_loader(self):
        model = SimpleNamespace(
            config=SimpleNamespace(projection_dim=512),
            to=lambda device: model,
            eval=lambda: None,
        )
        return model

    @override_settings(VISUAL_SEARCH_SEMANTIC_DEVICE="cpu")
    def test_cpu_mode_preserves_slow_processor(self):
        model = self._fake_loader()
        with patch("transformers.CLIPModel.from_pretrained", return_value=model) as load, \
             patch("transformers.CLIPProcessor.from_pretrained", return_value=object()) as processor:
            _load_model.cache_clear()
            loaded, _ = _load_model("approved-local-path")
        self.assertIs(loaded, model)
        load.assert_called_once_with("approved-local-path", local_files_only=True)
        processor.assert_called_once_with(
            "approved-local-path", local_files_only=True, use_fast=False
        )

    @override_settings(VISUAL_SEARCH_SEMANTIC_DEVICE="cuda")
    def test_forced_cuda_fails_closed_when_unavailable(self):
        with patch("torch.cuda.is_available", return_value=False), \
             patch("transformers.CLIPModel.from_pretrained", return_value=self._fake_loader()):
            _load_model.cache_clear()
            with self.assertRaisesRegex(RuntimeError, "CUDA device requested"):
                _load_model("approved-local-path")

    @override_settings(VISUAL_SEARCH_SEMANTIC_DEVICE="invalid")
    def test_invalid_device_setting_rejected(self):
        with patch("transformers.CLIPModel.from_pretrained", return_value=self._fake_loader()):
            _load_model.cache_clear()
            with self.assertRaisesRegex(RuntimeError, "must be auto, cpu or cuda"):
                _load_model("approved-local-path")
