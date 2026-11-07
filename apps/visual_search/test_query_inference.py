from types import SimpleNamespace
from unittest.mock import Mock, patch
from celery.exceptions import TimeoutError
from django.test import SimpleTestCase, override_settings
from .query_inference import remote_embed_text, validated_vector
from .query_tasks import encode_query
from .semantic import embed_text


@override_settings(VISUAL_SEARCH_SEMANTIC_ENABLED=True,
    VISUAL_SEARCH_SEMANTIC_POLICY_APPROVED=True,
    VISUAL_SEARCH_QUERY_BACKEND='celery', CELERY_AI_QUEUES_ENABLED=True,
    VISUAL_SEARCH_QUERY_TIMEOUT=5, VISUAL_SEARCH_SEMANTIC_MODEL_VERSION='clip-v1')
class RemoteQueryTests(SimpleTestCase):
    def test_web_uses_remote_queue_and_never_loads_model(self):
        result = Mock()
        result.get.return_value = {'model_version': 'clip-v1', 'vector': [0.1] * 512}
        with patch.object(encode_query, 'apply_async', return_value=result) as send, \
             patch('apps.visual_search.semantic._load_model', side_effect=AssertionError('web loaded model')):
            self.assertEqual(embed_text('a family portrait'), [0.1] * 512)
        self.assertEqual(send.call_args.kwargs['queue'], 'ai.query')
        self.assertEqual(send.call_args.kwargs['expires'], 30)
        self.assertNotIn('a family portrait', send.call_args.kwargs['argsrepr'])
        result.get.assert_called_once_with(timeout=5)
        result.forget.assert_called_once()

    def test_timeout_has_no_local_fallback(self):
        result = Mock()
        result.get.side_effect = TimeoutError()
        with patch.object(encode_query, 'apply_async', return_value=result), \
             patch('apps.visual_search.semantic._load_model', side_effect=AssertionError('fallback')):
            with self.assertRaises(TimeoutError):
                embed_text('a family portrait')
        result.forget.assert_called_once()

    def test_bad_results_fail_closed(self):
        for payload in ({'model_version':'other', 'vector':[0.1]*512},
                        {'model_version':'clip-v1', 'vector':[1]},
                        {'model_version':'clip-v1', 'vector':[float('nan')]*512}):
            result = Mock()
            result.get.return_value = payload
            with self.subTest(payload=str(payload)[:50]), patch.object(encode_query, 'apply_async', return_value=result):
                with self.assertRaises(ValueError):
                    remote_embed_text('portrait')
                result.forget.assert_called_once()

    def test_disabled_feature_or_routing_never_publishes(self):
        for setting in ('VISUAL_SEARCH_SEMANTIC_ENABLED', 'VISUAL_SEARCH_SEMANTIC_POLICY_APPROVED', 'CELERY_AI_QUEUES_ENABLED'):
            with self.subTest(setting=setting), override_settings(**{setting:False}), patch.object(encode_query, 'apply_async') as send:
                with self.assertRaises(RuntimeError):
                    remote_embed_text('portrait')
                send.assert_not_called()

    def test_worker_runs_local_inference_without_recursive_dispatch(self):
        vector = SimpleNamespace(tolist=lambda: [0.1]*512)
        with patch('apps.visual_search.semantic.embed_text_local', return_value=vector), patch.object(encode_query,'apply_async') as send:
            self.assertEqual(encode_query.run('portrait','clip-v1')['vector'], [0.1]*512)
            send.assert_not_called()

    def test_worker_rejects_wrong_version_and_invalid_query(self):
        with patch('apps.visual_search.semantic.embed_text_local') as local:
            for query, version in [('portrait','wrong'), ('x','clip-v1')]:
                with self.assertRaises(ValueError):
                    encode_query.run(query,version)
            local.assert_not_called()

    def test_vector_rejects_booleans_and_infinity(self):
        for vector in ([True]*512, [float('inf')]*512):
            with self.assertRaises(ValueError):
                validated_vector(vector)
