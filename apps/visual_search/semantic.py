"""Independent semantic-image vector store. Never stores face identity embeddings.

Operator must provision a reviewed CLIP-compatible model offline. No downloads.
Semantic data has independent gallery authorization and deletion controls.
"""
from functools import lru_cache
from django.conf import settings
from .vector_store import vector_connection

DIMENSION = 512

def semantic_enabled():
    return bool(getattr(settings, "VISUAL_SEARCH_SEMANTIC_ENABLED", False))

@lru_cache(maxsize=1)
def _load_model(path):
    from transformers import CLIPModel, CLIPProcessor
    if not path:
        raise RuntimeError("Approved semantic model is not configured")
    model = CLIPModel.from_pretrained(path, local_files_only=True)
    if model.config.projection_dim != DIMENSION:
        raise RuntimeError("Semantic model must produce 512-dimensional embeddings")
    model.eval()
    return model, CLIPProcessor.from_pretrained(path, local_files_only=True)


def embed_image(stream):
    if not semantic_enabled():
        raise RuntimeError("Semantic indexing is disabled")
    from PIL import Image, ImageOps
    import torch
    model, processor = _load_model(settings.VISUAL_SEARCH_SEMANTIC_MODEL_PATH)
    with Image.open(stream) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((2048, 2048))
        inputs = processor(images=img, return_tensors="pt")
    with torch.inference_mode():
        vector = model.get_image_features(**inputs)[0]
        vector = torch.nn.functional.normalize(vector, dim=0)
    return vector.cpu().numpy()


def embed_text(query):
    if not semantic_enabled():
        raise RuntimeError("Semantic search is disabled")
    import torch
    model, processor = _load_model(settings.VISUAL_SEARCH_SEMANTIC_MODEL_PATH)
    inputs = processor(text=[query], return_tensors="pt", padding=True, truncation=True)
    with torch.inference_mode():
        vector = model.get_text_features(**inputs)[0]
        vector = torch.nn.functional.normalize(vector, dim=0)
    return vector.cpu().numpy()

def replace_photo(*, photo, vector):
    import numpy as np
    from pgvector.psycopg import register_vector
    v = np.asarray(vector, dtype=np.float32)
    if v.shape != (DIMENSION,) or not np.isfinite(v).all():
        raise ValueError("Invalid semantic vector")
    with vector_connection() as conn:
        register_vector(conn)
        with conn.transaction():
            conn.execute("DELETE FROM visual_search.app_semantic_embeddings WHERE photo_id=%s", (photo.pk,))
            conn.execute("""INSERT INTO visual_search.app_semantic_embeddings
                (photo_id,gallery_id,model_version,embedding) VALUES (%s,%s,%s,%s)""",
                (photo.pk,photo.gallery_id,getattr(settings,"VISUAL_SEARCH_SEMANTIC_MODEL_VERSION","clip-v1"),v))

def purge_gallery(gallery_id):
    with vector_connection() as conn:
        conn.execute("DELETE FROM visual_search.app_semantic_embeddings WHERE gallery_id=%s",(gallery_id,))

def purge_photo(photo_id):
    with vector_connection() as conn:
        conn.execute("DELETE FROM visual_search.app_semantic_embeddings WHERE photo_id=%s",(photo_id,))
