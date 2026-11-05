"""Optional ONNX InsightFace-compatible detection and ArcFace inference.

Requires a separately licensed model pack, installed by the operator.
No model is downloaded at runtime.
"""
import io

from django.conf import settings
from PIL import Image, ImageOps


def extract_face_embeddings(stream):
    import numpy as np
    from insightface.app import FaceAnalysis

    if not settings.VISUAL_SEARCH_MODEL_PATH:
        raise RuntimeError("VISUAL_SEARCH_MODEL_PATH must point to licensed model files")
    Image.MAX_IMAGE_PIXELS = settings.VISUAL_SEARCH_MAX_IMAGE_PIXELS
    with Image.open(stream) as image:
        image = ImageOps.exif_transpose(image)
        image.load()
        if image.width * image.height > settings.VISUAL_SEARCH_MAX_IMAGE_PIXELS:
            raise ValueError("Image exceeds face indexing pixel limit")
        rgb = np.asarray(image.convert("RGB"))
    # InsightFace expects BGR images. The model pack must be provisioned offline.
    app = FaceAnalysis(name=settings.VISUAL_SEARCH_MODEL_PACK,
                       root=settings.VISUAL_SEARCH_MODEL_PATH, providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=-1, det_size=(640, 640))
    faces = app.get(rgb[:, :, ::-1].copy())
    vectors = []
    for face in faces:
        vec = np.asarray(face.normed_embedding, dtype=np.float32)
        if vec.shape != (512,) or not np.isfinite(vec).all():
            raise ValueError("Invalid 512-dimensional face embedding")
        vectors.append(vec.tolist())
    return vectors


def extract_face_review_crops(stream):
    """Ephemeral crops in the same face enumeration order as indexing.

    Crops alone are not evidence of index stability. Confirmation must also
    verify the stored embedding for that index matches this exact detection.
    """
    import base64
    import numpy as np
    from insightface.app import FaceAnalysis
    from io import BytesIO

    if not settings.VISUAL_SEARCH_MODEL_PATH:
        raise RuntimeError("Licensed face model is not configured")
    Image.MAX_IMAGE_PIXELS = settings.VISUAL_SEARCH_MAX_IMAGE_PIXELS
    with Image.open(stream) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.load()
        if image.width * image.height > settings.VISUAL_SEARCH_MAX_IMAGE_PIXELS:
            raise ValueError("Image exceeds review limit")
        rgb = np.asarray(image)
        app = FaceAnalysis(
            name=settings.VISUAL_SEARCH_MODEL_PACK,
            root=settings.VISUAL_SEARCH_MODEL_PATH,
            providers=["CPUExecutionProvider"],
        )
        app.prepare(ctx_id=-1, det_size=(640, 640))
        faces = app.get(rgb[:, :, ::-1].copy())
        output = []
        for index, face in enumerate(faces):
            box = [int(v) for v in face.bbox]
            left, top, right, bottom = box
            crop = image.crop((
                max(0, left), max(0, top),
                min(image.width, right), min(image.height, bottom),
            ))
            crop.thumbnail((200, 200))
            buffer = BytesIO()
            crop.save(buffer, format="JPEG", quality=78)
            output.append({
                "face_index": index,
                "preview": "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"),
                "embedding": np.asarray(face.normed_embedding, dtype=np.float32),
            })
        return output
