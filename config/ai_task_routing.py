"""Opt-in routing for model work; ordinary application tasks stay on celery."""


def ai_task_routes(enabled):
    if not enabled:
        return {}
    return {
        "apps.visual_search.semantic_tasks.*": {"queue": "ai.semantic"},
        "apps.visual_search.tasks.*": {"queue": "ai.face"},
    }
