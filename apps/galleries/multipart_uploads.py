import uuid

import boto3
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _client():
    if settings.GALLERY_STORAGE_BACKEND != "b2":
        raise ImproperlyConfigured("Direct multipart uploads require GALLERY_STORAGE_BACKEND=b2.")
    return boto3.client(
        "s3",
        aws_access_key_id=settings.B2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.B2_SECRET_ACCESS_KEY,
        region_name=settings.B2_REGION,
        endpoint_url=settings.B2_ENDPOINT_URL,
    )


def multipart_object_key(*, photographer_id, gallery_id, original_name, content_type):
    expected = ALLOWED_CONTENT_TYPES.get(content_type)
    if not expected:
        raise ValueError("Unsupported image content type.")
    # Object identity is independent of the client filename. Use the canonical
    # extension implied by the validated MIME type so names cannot drift.
    suffix = expected
    return (
        f"private/{settings.GALLERY_STORAGE_ENVIRONMENT}/galleries/"
        f"{photographer_id}/{gallery_id}/originals/{uuid.uuid4().hex}{suffix}"
    )


def initiate(*, key, content_type):
    return _client().create_multipart_upload(
        Bucket=settings.B2_BUCKET_NAME,
        Key=key,
        ContentType=content_type,
    )["UploadId"]


def sign_part(*, key, upload_id, part_number):
    return _client().generate_presigned_url(
        "upload_part",
        Params={
            "Bucket": settings.B2_BUCKET_NAME,
            "Key": key,
            "UploadId": upload_id,
            "PartNumber": part_number,
        },
        ExpiresIn=settings.B2_MULTIPART_SIGNED_URL_TTL,
        HttpMethod="PUT",
    )


def list_parts(*, key, upload_id):
    parts = []
    marker = None
    while True:
        params = {"Bucket": settings.B2_BUCKET_NAME, "Key": key, "UploadId": upload_id}
        if marker is not None:
            params["PartNumberMarker"] = marker
        response = _client().list_parts(**params)
        parts.extend(
            {"part_number": item["PartNumber"], "etag": item["ETag"], "size": item["Size"]}
            for item in response.get("Parts", [])
        )
        if not response.get("IsTruncated"):
            return parts
        marker = response.get("NextPartNumberMarker")


def get_object_bytes(*, key):
    """Read a completed object for server-side image validation."""
    response = _client().get_object(Bucket=settings.B2_BUCKET_NAME, Key=key)
    try:
        return response["Body"].read()
    finally:
        response["Body"].close()


def delete_object(*, key):
    return _client().delete_object(Bucket=settings.B2_BUCKET_NAME, Key=key)


def complete(*, key, upload_id, parts):
    return _client().complete_multipart_upload(
        Bucket=settings.B2_BUCKET_NAME,
        Key=key,
        UploadId=upload_id,
        MultipartUpload={"Parts": parts},
    )


def abort(*, key, upload_id):
    return _client().abort_multipart_upload(
        Bucket=settings.B2_BUCKET_NAME,
        Key=key,
        UploadId=upload_id,
    )
