"""Gallery-owner-scoped controls and text search, independent of biometric processing."""
import json
import logging
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from apps.galleries.models import Gallery, GalleryPhoto
from .models import GallerySemanticSearchPolicy, GalleryFaceSearchPolicy
from .semantic import semantic_enabled

logger = logging.getLogger(__name__)

def _owned(request, gallery_id):
    return Gallery.objects.filter(pk=gallery_id, photographer__user=request.user, deleted_at__isnull=True).first()

@login_required
@require_http_methods(["GET","POST"])
def discovery_settings(request, gallery_id):
    gallery = _owned(request, gallery_id)
    if gallery is None:
        return JsonResponse({"error":"not_found"},status=404)
    if request.method == "GET":
        semantic = GallerySemanticSearchPolicy.objects.filter(gallery=gallery).first()
        face = GalleryFaceSearchPolicy.objects.filter(gallery=gallery).first()
        return JsonResponse({
            "semantic_enabled": bool(semantic and semantic.processing_authorized),
            "semantic_available": semantic_enabled() and bool(getattr(settings,"VISUAL_SEARCH_SEMANTIC_POLICY_APPROVED",False)),
            "facial_enabled": bool(face and face.processing_authorized),
            "facial_available": bool(getattr(settings,"VISUAL_SEARCH_FACE_INDEXING_ENABLED",False)),
            "facial_settings_read_only": True,
        })
    try:
        payload=json.loads(request.body)
    except (ValueError,UnicodeDecodeError):
        return JsonResponse({"error":"invalid_json"},status=400)
    if not isinstance(payload,dict) or type(payload.get("semantic_enabled")) is not bool or set(payload)-{"semantic_enabled"}:
        return JsonResponse({"error":"invalid_settings"},status=400)
    enabled=payload["semantic_enabled"]
    if enabled and not (semantic_enabled() and getattr(settings,"VISUAL_SEARCH_SEMANTIC_POLICY_APPROVED",False)):
        return JsonResponse({"error":"semantic_unavailable"},status=403)
    with transaction.atomic():
        gallery=Gallery.objects.select_for_update().get(pk=gallery.pk)
        policy,_=GallerySemanticSearchPolicy.objects.get_or_create(gallery=gallery)
        policy.processing_authorized=enabled
        policy.save()
        if not enabled:
            from .semantic_tasks import purge_semantic_gallery
            transaction.on_commit(lambda: purge_semantic_gallery.delay(gallery.pk))
        else:
            from .semantic_tasks import index_semantic_gallery
            transaction.on_commit(lambda: index_semantic_gallery.delay(gallery.pk))
    return JsonResponse({"semantic_enabled":enabled,"facial_settings_read_only":True})

@login_required
@require_http_methods(["GET"])
def semantic_search(request, gallery_id):
    gallery = _owned(request,gallery_id)
    if gallery is None:
        return JsonResponse({"error":"not_found"},status=404)
    if not semantic_enabled() or not getattr(settings,"VISUAL_SEARCH_SEMANTIC_POLICY_APPROVED",False):
        return JsonResponse({"error":"unavailable"},status=503)
    if not GallerySemanticSearchPolicy.objects.filter(gallery=gallery,processing_authorized=True).exists():
        return JsonResponse({"error":"disabled"},status=403)
    query=request.GET.get("q","").strip()
    if not 2 <= len(query) <= 200:
        return JsonResponse({"error":"invalid_query"},status=400)
    try:
        import numpy as np
        from pgvector.psycopg import register_vector
        from .semantic import embed_text
        vector=np.asarray(embed_text(query),dtype=np.float32)
        with __import__("apps.visual_search.vector_store",fromlist=["vector_connection"]).vector_connection() as conn:
            register_vector(conn)
            rows=conn.execute("""SELECT photo_id FROM visual_search.app_semantic_embeddings
              WHERE gallery_id=%s AND model_version=%s ORDER BY embedding <=> %s LIMIT 100""",
              (gallery.pk,getattr(settings,"VISUAL_SEARCH_SEMANTIC_MODEL_VERSION","clip-v1"),vector)).fetchall()
        ids=[r[0] for r in rows]
        allowed=set(GalleryPhoto.objects.filter(pk__in=ids,gallery=gallery,status=GalleryPhoto.Status.COMPLETED).values_list("pk",flat=True))
        return JsonResponse({"photo_ids":[i for i in ids if i in allowed]})
    except Exception:
        logger.exception("Semantic search unavailable")
        return JsonResponse({"error":"unavailable"},status=503)

def _semantic_results(gallery, query):
    import numpy as np
    from pgvector.psycopg import register_vector
    from .semantic import embed_text
    from .vector_store import vector_connection
    vector=np.asarray(embed_text(query),dtype=np.float32)
    with vector_connection() as conn:
        register_vector(conn)
        rows=conn.execute("""SELECT photo_id FROM visual_search.app_semantic_embeddings
            WHERE gallery_id=%s AND model_version=%s
            ORDER BY embedding <=> %s LIMIT 100""",
            (gallery.pk,getattr(settings,"VISUAL_SEARCH_SEMANTIC_MODEL_VERSION","clip-v1"),vector)).fetchall()
    ids=[r[0] for r in rows]
    allowed=set(GalleryPhoto.objects.filter(
        pk__in=ids,gallery=gallery,status=GalleryPhoto.Status.COMPLETED,is_visible=True
    ).values_list("pk",flat=True))
    return [i for i in ids if i in allowed][:40]

def _client_semantic(request, gallery):
    from apps.galleries.models import GalleryPermission
    from django.utils import timezone
    if not semantic_enabled() or not getattr(settings,"VISUAL_SEARCH_SEMANTIC_POLICY_APPROVED",False):
        return JsonResponse({"error":"unavailable"},status=503)
    if gallery.deleted_at or gallery.archived_at or gallery.status not in (Gallery.Status.PUBLISHED,Gallery.Status.DELIVERED):
        return JsonResponse({"error":"not_found"},status=404)
    permission=GalleryPermission.objects.filter(gallery=gallery).first()
    if not permission or not permission.view_gallery:
        return JsonResponse({"error":"not_found"},status=404)
    if gallery.expires_at and gallery.expires_at <= timezone.now() and permission.automatic_gallery_lock:
        return JsonResponse({"error":"not_found"},status=404)
    if not GallerySemanticSearchPolicy.objects.filter(gallery=gallery,processing_authorized=True).exists():
        return JsonResponse({"error":"disabled"},status=403)
    query=request.GET.get("q","").strip()
    if not 2 <= len(query) <= 200:
        return JsonResponse({"error":"invalid_query"},status=400)
    try:
        ids=_semantic_results(gallery,query)
        # Recheck authorization after the vector read.
        if not GallerySemanticSearchPolicy.objects.filter(gallery=gallery,processing_authorized=True).exists():
            return JsonResponse({"error":"disabled"},status=403)
        photos={p.pk:p for p in GalleryPhoto.objects.filter(pk__in=ids,gallery=gallery,is_visible=True,status=GalleryPhoto.Status.COMPLETED)}
        return JsonResponse({"results":[{"photo_id":i,"thumbnail_url":photos[i].thumbnail_url} for i in ids if i in photos]})
    except Exception:
        logger.exception("Client semantic search unavailable")
        return JsonResponse({"error":"unavailable"},status=503)

@require_http_methods(["GET"])
def public_semantic_search(request, public_id):
    from django.shortcuts import get_object_or_404
    gallery=get_object_or_404(Gallery,public_id=public_id,visibility=Gallery.Visibility.PUBLIC)
    return _client_semantic(request,gallery)

@require_http_methods(["GET"])
def invited_semantic_search(request, token):
    from django.http import Http404
    from apps.galleries.views import _client_gallery_access
    try:
        _,_,gallery,_,_=_client_gallery_access(token)
    except Http404:
        return JsonResponse({"error":"not_found"},status=404)
    return _client_semantic(request,gallery)
