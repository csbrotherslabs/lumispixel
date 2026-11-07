"""Small JSON-only web/worker boundary; no model dependencies on the web host."""
import math
from django.conf import settings


def validated_vector(vector):
    if not isinstance(vector, (list, tuple)) or len(vector) != 512:
        raise ValueError("Invalid semantic embedding dimensions")
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in vector):
        raise ValueError("Invalid semantic embedding values")
    return [float(v) for v in vector]


def remote_embed_text(query):
    if not settings.VISUAL_SEARCH_SEMANTIC_ENABLED or not settings.VISUAL_SEARCH_SEMANTIC_POLICY_APPROVED:
        raise RuntimeError("Semantic search is disabled")
    if not settings.CELERY_AI_QUEUES_ENABLED:
        raise RuntimeError("Dedicated AI routing is required")
    if not isinstance(query, str) or not 2 <= len(query.strip()) <= 200:
        raise ValueError("Invalid semantic query")
    from .query_tasks import encode_query
    version = settings.VISUAL_SEARCH_SEMANTIC_MODEL_VERSION
    result = encode_query.apply_async(
        args=[query, version], queue="ai.query", expires=30,
        argsrepr="[<redacted query>, <model version>]",
        retry=False,
    )
    try:
        payload = result.get(timeout=settings.VISUAL_SEARCH_QUERY_TIMEOUT)
        if not isinstance(payload, dict) or payload.get("model_version") != version:
            raise ValueError("Semantic model version mismatch")
        return validated_vector(payload.get("vector"))
    finally:
        result.forget()
