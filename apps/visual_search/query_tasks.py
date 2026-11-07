"""Dedicated interactive inference; permission checks and SQL stay on the web."""
from celery import shared_task
from django.conf import settings
from .query_inference import validated_vector


@shared_task(soft_time_limit=20, time_limit=25, expires=30)
def encode_query(query, model_version):
    if not settings.VISUAL_SEARCH_SEMANTIC_ENABLED or not settings.VISUAL_SEARCH_SEMANTIC_POLICY_APPROVED:
        raise RuntimeError("Semantic search is disabled")
    if model_version != settings.VISUAL_SEARCH_SEMANTIC_MODEL_VERSION:
        raise ValueError("Semantic model version mismatch")
    if not isinstance(query, str) or not 2 <= len(query.strip()) <= 200:
        raise ValueError("Invalid semantic query")
    from .semantic import embed_text_local
    vector = validated_vector(embed_text_local(query).tolist())
    return {"model_version": model_version, "vector": vector}
